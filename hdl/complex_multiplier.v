`timescale 1ns/1ps

`ifdef VERILATOR  // make parameter readable from VPI
  `define VL_RD /*verilator public_flat_rd*/
`else
  `define VL_RD
`endif

module complex_multiplier
    #(parameter INPUT_WIDTH_A `VL_RD = 16, // must be multiple of 8
      parameter INPUT_WIDTH_B `VL_RD = 16, // must be multiple of 8
      parameter OUTPUT_WIDTH `VL_RD = 32,  // must be multiple of 8
      parameter STAGES `VL_RD = 3,  // minimum value is 2
      parameter BLOCKING `VL_RD = 1,
      parameter TRUNCATE `VL_RD = 1)
    (   
        input wire             clk, nrst,
		inout wire				rounding_cy,
        // slave a
        input signed            [INPUT_WIDTH_A-1:0] s_axis_a_tdata,
        output reg                            s_axis_a_tready,
        input wire                            s_axis_a_tvalid,
        // slave b
        input signed            [INPUT_WIDTH_B-1:0] s_axis_b_tdata,
        output reg                            s_axis_b_tready,
        input wire                            s_axis_b_tvalid,
        // master output
        output reg signed		  [OUTPUT_WIDTH-1:0] m_axis_tdata,
        output reg                          m_axis_tvalid,
        input wire                           m_axis_tready
        );
    // p = a*b = p_r + jp_i = (a_r*b_r - a_i*b_i) + j(a_r*b_i + a_i*b_r)
    // stage1: calculate a_r*b_r, a_i*b_i, a_r*b_i, a_i*b_r
    // stage2: calculate p_r and p_i

    reg        [STAGES:0]                      tvalid;
    reg        [OUTPUT_WIDTH-1:0]              tdata [STAGES-2:0];

    wire signed [INPUT_WIDTH_A/2-1:0] a_r;
    wire signed [INPUT_WIDTH_A/2-1:0] a_i;
    wire signed [INPUT_WIDTH_B/2-1:0] b_r;
    wire signed [INPUT_WIDTH_B/2-1:0] b_i;
    assign a_i = s_axis_a_tdata[INPUT_WIDTH_A-1:INPUT_WIDTH_A/2];
    assign a_r = s_axis_a_tdata[INPUT_WIDTH_A/2-1:0];
    assign b_i = s_axis_b_tdata[INPUT_WIDTH_B-1:INPUT_WIDTH_B/2];
    assign b_r = s_axis_b_tdata[INPUT_WIDTH_B/2-1:0];
    
    localparam TRUNC_BITS = INPUT_WIDTH_A + INPUT_WIDTH_B - OUTPUT_WIDTH;

    // intermediate products are calculated with full precision, this can be optimized in the case of truncation
    // the synthesizer hopefully does this optimization
    reg signed [INPUT_WIDTH_A+INPUT_WIDTH_B-1:0] ar_br, ai_bi, ar_bi, ai_br;

    wire signed [OUTPUT_WIDTH/2-1:0] result_r;
    wire signed [OUTPUT_WIDTH/2-1:0] result_i;
    wire signed [INPUT_WIDTH_A+INPUT_WIDTH_B-1:0] temp1,temp2;
	if (TRUNCATE==1) begin
		assign temp1 = (ar_br - ai_bi)>>>TRUNC_BITS;
		assign temp2 = (ar_bi + ai_br)>>>TRUNC_BITS;  
		assign result_r = temp1[OUTPUT_WIDTH/2-1:0];
		assign result_i = temp2[OUTPUT_WIDTH/2-1:0];    
	end
	else begin
		assign temp1 = (ar_br - ai_bi + {{1'b0},{TRUNC_BITS-2},{rounding_cy}})>>>TRUNC_BITS;
		assign temp2 = (ar_bi + ai_br + {{1'b0},{TRUNC_BITS-2},{rounding_cy}})>>>TRUNC_BITS;
		assign result_r = temp1[OUTPUT_WIDTH/2-1:0];
		assign result_i = temp2[OUTPUT_WIDTH/2-1:0];    
	end


    integer i;
    always @(posedge clk) begin
        if (nrst == 0) begin
            m_axis_tdata <= {(OUTPUT_WIDTH){1'b0}};
            m_axis_tvalid <= 0;
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
            if (BLOCKING == 1 && m_axis_tready == 0 && m_axis_tvalid == 1) begin 
                m_axis_tvalid <= 0;
                m_axis_tdata <= {(OUTPUT_WIDTH){1'b0}};
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
                m_axis_tvalid <= tvalid[STAGES-2];
                
                // propagate data through pipeline, 1 cycle is already used for calculation
                if (STAGES > 2) begin
                    tdata[0] <= {result_i,result_r};
                    for (i = 1; i<(STAGES-2); i = i+1) begin
                        tdata[i] <= tdata[i-1];
                    end
                    m_axis_tdata <= tdata[STAGES-3];
                end
                else begin
                    m_axis_tdata <= {result_i,result_r};
                end
            end
        end
    end
endmodule