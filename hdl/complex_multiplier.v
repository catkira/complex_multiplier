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
      parameter integer ROUND_MODE `VL_RD = 0)
    (   
        input               aclk,
        input               aresetn,
		input               rounding_cy,
        // slave a
        input               [((OPERAND_WIDTH_A*2+15)/16)*16-1:0] s_axis_a_tdata, // round operands up to multiple of 8
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
    localparam TRUNC_BITS = (INPUT_WIDTH_A + INPUT_WIDTH_B + 2 - OUTPUT_WIDTH)/2;
    localparam AXIS_OUTPUT_WIDTH = ((OUTPUT_WIDTH+15)/16)*16;  // round operands up to multiple of 8
    localparam AXIS_INPUT_WIDTH_A = ((INPUT_WIDTH_A+15)/16)*16;
    localparam AXIS_INPUT_WIDTH_B = ((INPUT_WIDTH_B+15)/16)*16;
    localparam OUTPUT_PADDING = AXIS_OUTPUT_WIDTH - OUTPUT_WIDTH;

    // output pipeline
    reg        [STAGES:0]                      tvalid;
    reg        [AXIS_OUTPUT_WIDTH-1:0]         tdata [STAGES-2:0];

    wire signed [OPERAND_WIDTH_A-1:0] a_r = s_axis_a_tdata[OPERAND_WIDTH_A - 1 : 0];;
    wire signed [OPERAND_WIDTH_A-1:0] a_i = s_axis_a_tdata[AXIS_INPUT_WIDTH_A / 2 + OPERAND_WIDTH_A - 1 : AXIS_INPUT_WIDTH_A / 2];
    wire signed [OPERAND_WIDTH_B-1:0] b_r = s_axis_b_tdata[OPERAND_WIDTH_B - 1 : 0];
    wire signed [OPERAND_WIDTH_B-1:0] b_i = s_axis_b_tdata[AXIS_INPUT_WIDTH_B / 2 + OPERAND_WIDTH_B - 1 : AXIS_INPUT_WIDTH_B / 2];

    // intermediate products are calculated with full precision, this can be optimized in the case of truncation
    // the synthesizer hopefully does this optimization
    reg signed [OPERAND_WIDTH_A + OPERAND_WIDTH_B : 0] ar_br, ai_bi, ar_bi, ai_br;
    reg signed [OPERAND_WIDTH_A - 1 : 0] a_r_buf, a_i_buf;
    reg signed [OPERAND_WIDTH_B - 1 : 0] b_r_buf, b_i_buf;
    reg                          a_valid_buf, b_valid_buf;
    reg                          rounding_cy_buf, rounding_cy_buf2;

    wire signed [OPERAND_WIDTH_OUT - 1 : 0] result_r;
    wire signed [OPERAND_WIDTH_OUT - 1 : 0] result_i;
    wire signed [OPERAND_WIDTH_A + OPERAND_WIDTH_B + 1 - 1 : 0] temp1, temp2;
    wire signed [OPERAND_WIDTH_A + OPERAND_WIDTH_B + 1 - 1 : 0] point5_correction = {{(OPERAND_WIDTH_A + OPERAND_WIDTH_B + 1 - TRUNC_BITS){1'b0}}, rounding_cy_buf2, {(TRUNC_BITS-1){~rounding_cy_buf2}}};
	if (ROUND_MODE == 0 || TRUNC_BITS == 0) begin
		assign temp1 = (ar_br - ai_bi) >>> TRUNC_BITS;
		assign temp2 = (ar_bi + ai_br) >>> TRUNC_BITS;  
		assign result_r = temp1[OPERAND_WIDTH_OUT - 1 : 0];
		assign result_i = temp2[OPERAND_WIDTH_OUT - 1 : 0];    
	end
	else begin
        // add 0.5 if rounding cy == 1, else add 0.499999999
        assign temp1 = (ar_br - ai_bi + point5_correction) >>> TRUNC_BITS;
        assign temp2 = (ar_bi + ai_br + point5_correction) >>> TRUNC_BITS;
		assign result_r = temp1[OPERAND_WIDTH_OUT-1:0];
		assign result_i = temp2[OPERAND_WIDTH_OUT-1:0];    
	end


    integer i;
    always @(posedge aclk) begin
        if (aresetn == 0) begin
            tvalid <= {{(STAGES+1){1'b0}}};
            a_valid_buf <= 0;
            b_valid_buf <= 0;
        end
        else begin
            // always take data into input pipeline
            a_r_buf <= a_r;
            a_i_buf <= a_i;
            b_r_buf <= b_r;
            b_i_buf <= b_i;
            if (ROUND_MODE == 1)
                rounding_cy_buf <= rounding_cy;

            a_valid_buf <= s_axis_a_tvalid;
            b_valid_buf <= s_axis_b_tvalid;
            rounding_cy_buf <= rounding_cy;
            rounding_cy_buf2 <= rounding_cy_buf;

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


                ar_br <= a_r_buf * b_r_buf;
                ai_bi <= a_i_buf * b_i_buf;
                ar_bi <= a_r_buf * b_i_buf;
                ai_br <= a_i_buf * b_r_buf;
                
                // propagate valid bit through pipeline
                // if BLOCKING is enabled the inputs are only sampled when both inputs are valid at the same time
                // when only one input is valid, the output wont have valid set
                // if only one input is valid, data loss occurs!
                // TODO: Implement separate sampling of input channels and then wait until both are sampled
                // if BLOCKING is disabled, input data is sampled even if only one input is valid
                if (BLOCKING == 1) begin
                    tvalid[0] <= a_valid_buf & b_valid_buf;
                end
                else begin
                    tvalid[0] <= a_valid_buf | b_valid_buf;
                end
                for (i = 1; i<(STAGES); i = i+1) begin
                    tvalid[i] <= tvalid[i-1];
                end
                m_axis_dout_tvalid <= tvalid[STAGES-2];
                
                // propagate data through pipeline, 1 cycle is already used for calculation
                if (STAGES > 2) begin
                    tdata[0] <= {{(OUTPUT_PADDING/2){result_i[OPERAND_WIDTH_OUT - 1]}}, result_i,
                        {(OUTPUT_PADDING/2){result_r[OPERAND_WIDTH_OUT - 1]}}, result_r};
                    for (i = 1; i<(STAGES-2); i = i+1) begin
                        tdata[i] <= tdata[i-1];
                    end
                    m_axis_dout_tdata <= tdata[STAGES-3];
                end
                else begin
                    m_axis_dout_tdata <= {{(OUTPUT_PADDING/2){result_i[OPERAND_WIDTH_OUT - 1]}}, result_i,
                        {(OUTPUT_PADDING/2){result_r[OPERAND_WIDTH_OUT - 1]}}, result_r};
                end
            end
        end
    end
endmodule