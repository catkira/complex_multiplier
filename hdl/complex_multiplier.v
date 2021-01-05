`timescale 1ns/1ps

`ifdef VERILATOR  // make parameter readable from VPI
  `define VL_RD /*verilator public_flat_rd*/
`else
  `define VL_RD
`endif

module complex_multiplier
    #(parameter integer OPERAND_WIDTH_A `VL_RD = 16, // must be multiple of 2
      parameter integer OPERAND_WIDTH_B `VL_RD = 16, // must be multiple of 2
      parameter integer OPERAND_WIDTH_OUT `VL_RD = 32,  // must be multiple of 8
      parameter integer STAGES `VL_RD = 3,  // minimum value is 2
      parameter integer BLOCKING `VL_RD = 1,
      parameter integer TRUNCATE `VL_RD = 1)
    (   
        input               aclk, aresetn,
		input               rounding_cy,
        // slave a
        input               [((OPERAND_WIDTH_A*2+15)/16)*16-1:0] s_axis_a_tdata,
        output reg                            s_axis_a_tready,
        input                                   s_axis_a_tvalid,
        // slave b
        input               [((OPERAND_WIDTH_B*2+15)/16)*16-1:0] s_axis_b_tdata,
        output reg                            s_axis_b_tready,
        input                                 s_axis_b_tvalid,
        // master output
        output reg  		  [((OPERAND_WIDTH_OUT*2+15)/16)*16-1:0] m_axis_dout_tdata,
        output reg                          m_axis_dout_tvalid,
        input                              m_axis_dout_tready
        );
    // p = a*b = p_r + jp_i = (a_r*b_r - a_i*b_i) + j(a_r*b_i + a_i*b_r)
    // stage1: calculate a_r*b_r, a_i*b_i, a_r*b_i, a_i*b_r
    // stage2: calculate p_r and p_i
    localparam INPUT_WIDTH_A = 2*OPERAND_WIDTH_A;
    localparam INPUT_WIDTH_B = 2*OPERAND_WIDTH_B;
    localparam OUTPUT_WIDTH = 2*OPERAND_WIDTH_OUT;
    localparam TRUNC_BITS = (INPUT_WIDTH_A + INPUT_WIDTH_B - OUTPUT_WIDTH)/2;
    localparam AXIS_OUTPUT_WIDTH = ((OUTPUT_WIDTH+15)/16)*16;
    localparam AXIS_INPUT_WIDTH_A = ((INPUT_WIDTH_A+15)/16)*16;
    localparam AXIS_INPUT_WIDTH_B = ((INPUT_WIDTH_B+15)/16)*16;
    localparam OUTPUT_PADDING = AXIS_OUTPUT_WIDTH - OUTPUT_WIDTH;

    reg        [STAGES:0]                      tvalid;
    reg        [AXIS_OUTPUT_WIDTH-1:0]         tdata [STAGES-2:0];

    wire signed [INPUT_WIDTH_A/2-1:0] a_r;
    wire signed [INPUT_WIDTH_A/2-1:0] a_i;
    wire signed [INPUT_WIDTH_B/2-1:0] b_r;
    wire signed [INPUT_WIDTH_B/2-1:0] b_i;
    assign a_i = s_axis_a_tdata[AXIS_INPUT_WIDTH_A/2 + INPUT_WIDTH_A/2 - 1:AXIS_INPUT_WIDTH_A/2];
    // assign a_i = s_axis_a_tdata[INPUT_WIDTH_A-1:INPUT_WIDTH_A/2];
    assign a_r = s_axis_a_tdata[INPUT_WIDTH_A/2-1:0];
    // assign b_i = s_axis_b_tdata[INPUT_WIDTH_B-1:INPUT_WIDTH_B/2];
    assign b_i = s_axis_b_tdata[AXIS_INPUT_WIDTH_B/2 + INPUT_WIDTH_B/2 - 1:AXIS_INPUT_WIDTH_B/2];
    assign b_r = s_axis_b_tdata[INPUT_WIDTH_B/2-1:0];
    

    // intermediate products are calculated with full precision, this can be optimized in the case of truncation
    // the synthesizer hopefully does this optimization
    reg signed [INPUT_WIDTH_A+INPUT_WIDTH_B-1:0] ar_br, ai_bi, ar_bi, ai_br;

    wire signed [OUTPUT_WIDTH/2-1:0] result_r;
    wire signed [OUTPUT_WIDTH/2-1:0] result_i;
    wire signed [INPUT_WIDTH_A+INPUT_WIDTH_B-1:0] temp1,temp2;
	if (TRUNCATE == 1 || TRUNC_BITS == 0) begin
		assign temp1 = (ar_br - ai_bi)>>>TRUNC_BITS;
		assign temp2 = (ar_bi + ai_br)>>>TRUNC_BITS;  
		assign result_r = temp1[OUTPUT_WIDTH/2-1:0];
		assign result_i = temp2[OUTPUT_WIDTH/2-1:0];    
	end
	else begin
		assign temp1 = (ar_br - ai_bi + {{(INPUT_WIDTH_A+INPUT_WIDTH_B-2-TRUNC_BITS){1'b0}},{1'b0},{(TRUNC_BITS-1){1'b1}},{rounding_cy}})>>>TRUNC_BITS;
		assign temp2 = (ar_bi + ai_br + {{(INPUT_WIDTH_A+INPUT_WIDTH_B-2-TRUNC_BITS){1'b0}},{1'b0},{(TRUNC_BITS-1){1'b1}},{rounding_cy}})>>>TRUNC_BITS;
		assign result_r = temp1[OUTPUT_WIDTH/2-1:0];
		assign result_i = temp2[OUTPUT_WIDTH/2-1:0];    
	end


    integer i;
    always @(posedge aclk) begin
        if (aresetn == 0) begin
            m_axis_dout_tdata <= {(OUTPUT_WIDTH){1'b0}};
            m_axis_dout_tvalid <= 0;
            tvalid <= {{(STAGES+1){1'b0}}};
            for (i=0;i<(STAGES-1);i=i+1)
                tdata[i] <= {OUTPUT_WIDTH{1'b0}};
            ai_bi <= {(INPUT_WIDTH_A+INPUT_WIDTH_B){1'b0}};
            ai_br <= {(INPUT_WIDTH_A+INPUT_WIDTH_B){1'b0}};
            ar_bi <= {(INPUT_WIDTH_A+INPUT_WIDTH_B){1'b0}};
            ar_br <= {(INPUT_WIDTH_A+INPUT_WIDTH_B){1'b0}};
        end
        else begin
            // wait for receiver to be ready if BLOCKING is enabled
            if (BLOCKING == 1 && m_axis_dout_tready == 0 && m_axis_dout_tvalid == 1) begin 
                m_axis_dout_tvalid <= 0;
                m_axis_dout_tdata <= {(OUTPUT_WIDTH){1'b0}};
                // apply back pressure
                s_axis_a_tready <= 0;
                s_axis_b_tready <= 0;
            end
            else begin
                s_axis_a_tready <= 1;
                s_axis_b_tready <= 1;
                ar_br <= a_r * b_r;
                ai_bi <= a_i * b_i;
                ar_bi <= a_r * b_i;
                ai_br <= a_i * b_r;
                
                // propagate valid bit through pipeline
                // if BLOCKING is enabled the inputs are only sampled when both inputs are valid at the same time
                // when only one input is valid, the output wont have valid set
                // if only one input is valid, data loss occurs!
                // TODO: Implement separate sampling of input channels and then wait until both are sampled
                // if BLOCKING is disabled, input data is sampled even if only one input is valid
                if (BLOCKING == 1) begin
                    tvalid[0] <= s_axis_a_tvalid & s_axis_b_tvalid;
                end
                else begin
                    tvalid[0] <= s_axis_a_tvalid | s_axis_b_tvalid;
                end
                for (i = 1; i<(STAGES); i = i+1) begin
                    tvalid[i] <= tvalid[i-1];
                end
                m_axis_dout_tvalid <= tvalid[STAGES-2];
                
                // propagate data through pipeline, 1 cycle is already used for calculation
                if (STAGES > 2) begin
                    tdata[0] <= {{(OUTPUT_PADDING/2){result_i[OUTPUT_WIDTH/2 - 1]}}, result_i,
                        {(OUTPUT_PADDING/2){result_r[OUTPUT_WIDTH/2 - 1]}}, result_r};
                    for (i = 1; i<(STAGES-2); i = i+1) begin
                        tdata[i] <= tdata[i-1];
                    end
                    m_axis_dout_tdata <= tdata[STAGES-3];
                end
                else begin
                    m_axis_dout_tdata <= {{(OUTPUT_PADDING/2){result_i[OUTPUT_WIDTH/2 - 1]}}, result_i,
                        {(OUTPUT_PADDING/2){result_r[OUTPUT_WIDTH/2 - 1]}}, result_r};
                end
            end
        end
    end
endmodule