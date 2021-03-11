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
      parameter integer STAGES `VL_RD = 6,  // minimum value is 6
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
    localparam CALCULATION_STAGES = 6;    

    // output pipeline
    reg        [STAGES:0]                      tvalid;
    reg        [AXIS_OUTPUT_WIDTH-1:0]         tdata [STAGES-2:0];

    wire signed [OPERAND_WIDTH_A-1:0] a_r = s_axis_a_tdata[OPERAND_WIDTH_A - 1 : 0];;
    wire signed [OPERAND_WIDTH_A-1:0] a_i = s_axis_a_tdata[AXIS_INPUT_WIDTH_A / 2 + OPERAND_WIDTH_A - 1 : AXIS_INPUT_WIDTH_A / 2];
    wire signed [OPERAND_WIDTH_B-1:0] b_r = s_axis_b_tdata[OPERAND_WIDTH_B - 1 : 0];
    wire signed [OPERAND_WIDTH_B-1:0] b_i = s_axis_b_tdata[AXIS_INPUT_WIDTH_B / 2 + OPERAND_WIDTH_B - 1 : AXIS_INPUT_WIDTH_B / 2];

    // intermediate products are calculated with full precision, this can be optimized in the case of truncation
    // the synthesizer hopefully does this optimization
    reg signed [OPERAND_WIDTH_A + OPERAND_WIDTH_B : 0] mult_r, mult_i, mult_0, common, common_r1, common_r2, p_r_int, p_i_int;
    reg signed [OPERAND_WIDTH_A - 1 : 0] a_r_d, a_i_d, a_r_dd, a_i_dd, a_r_ddd, a_i_ddd, a_r_dddd, a_i_dddd;
    reg signed [OPERAND_WIDTH_B - 1 : 0] b_r_d, b_i_d, b_r_dd, b_i_dd, b_r_ddd, b_i_ddd;
    reg                          a_valid_d, b_valid_d;
    reg signed [OPERAND_WIDTH_A : 0] a_dd_common;
    reg signed [OPERAND_WIDTH_B : 0] a_dd_r, a_dd_i;
    reg        [STAGES - 1 : 0]  rounding_cy_buf ;

    wire signed [OPERAND_WIDTH_OUT - 1 : 0] result_r;
    wire signed [OPERAND_WIDTH_OUT - 1 : 0] result_i;
    wire signed [OPERAND_WIDTH_A + OPERAND_WIDTH_B + 1 - 1 : 0] temp1, temp2;
    localparam rounding_cy_buf_index = CALCULATION_STAGES - 1;
    wire signed [OPERAND_WIDTH_A + OPERAND_WIDTH_B + 1 - 1 : 0] rounding_cy_extended = {{(OPERAND_WIDTH_A + OPERAND_WIDTH_B){1'b0}}, rounding_cy_buf[rounding_cy_buf_index]};
    // round_cy decides if point5_correction is 0.5 (-> round half up) or 0.49999999999 (-> round half down)
    wire signed [OPERAND_WIDTH_A + OPERAND_WIDTH_B + 1 - 1 : 0] point5_correction = {{(OPERAND_WIDTH_A + OPERAND_WIDTH_B + 1 - TRUNC_BITS){1'b0}}, 1'b0, {(TRUNC_BITS-1){1'b1}}} + rounding_cy_extended;
	if (ROUND_MODE == 0 || TRUNC_BITS == 0) begin
        assign temp1 = p_r_int >>> TRUNC_BITS;
        assign temp2 = p_i_int >>> TRUNC_BITS;
		assign result_r = temp1[OPERAND_WIDTH_OUT - 1 : 0];
		assign result_i = temp2[OPERAND_WIDTH_OUT - 1 : 0];    
	end
	else begin
        // add 0.5 if rounding cy == 1, else add 0.499999999
        assign temp1 = (p_r_int + point5_correction) >>> TRUNC_BITS;
        assign temp2 = (p_i_int + point5_correction) >>> TRUNC_BITS;
		assign result_r = temp1[OPERAND_WIDTH_OUT-1:0];
		assign result_i = temp2[OPERAND_WIDTH_OUT-1:0];    
	end

    integer i;
    always @(posedge aclk) begin
        if (aresetn == 0) begin
            tvalid <= {{(STAGES+1){1'b0}}};
            a_valid_d <= 0;
            b_valid_d <= 0;
        end
        else begin
            // stage 1
            a_valid_d <= s_axis_a_tvalid;
            b_valid_d <= s_axis_b_tvalid;
            a_r_d <= a_r;
            a_i_d <= a_i;
            b_r_d <= b_r;
            b_i_d <= b_i;
            if (ROUND_MODE == 1)
                rounding_cy_buf[0] <= rounding_cy;
            else if (ROUND_MODE == 2)  // clock divider
                rounding_cy_buf[0] <= ~rounding_cy_buf[0];

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

                // stage 2
                a_dd_common <= a_r_d - a_i_d;
                a_r_dd <= a_r_d;
                a_i_dd <= a_i_d;
                b_r_dd <= b_r_d;
                b_i_dd <= b_i_d;

                // stage 3
                a_r_ddd <= a_r_dd;
                a_i_ddd <= a_i_dd;
                b_r_ddd <= b_r_dd;
                b_i_ddd <= b_i_dd;
                mult_0 <= a_dd_common * b_i_dd;

                // stage 4
                a_r_dddd <= a_r_ddd;
                a_i_dddd <= a_i_ddd;
                a_dd_r <= b_r_ddd - b_i_ddd;
                a_dd_i <= b_r_ddd + b_i_ddd;
                common <= mult_0;

                // stage 5
                mult_r <= a_dd_r * a_r_dddd;
                mult_i <= a_dd_i * a_i_dddd;
                common_r1 <= common;
                common_r2 <= common;

                // stage 6
                p_r_int <= mult_r + common_r1;
                p_i_int <= mult_i + common_r2;

                for (i = 1; i<STAGES; i = i + 1) begin
                    rounding_cy_buf[i] <= rounding_cy_buf[i-1];
                end
                
                // stages 1-6
                tvalid[0] <= a_valid_d & b_valid_d;
                for (i = 1; i<(STAGES); i = i+1) begin
                    tvalid[i] <= tvalid[i-1];
                end
                m_axis_dout_tvalid <= tvalid[STAGES-2];
                
                // propagate data through pipeline, 1 cycle is already used for calculation

                if (STAGES > CALCULATION_STAGES) begin
                    tdata[0] <= {{(OUTPUT_PADDING/2){result_i[OPERAND_WIDTH_OUT - 1]}}, result_i,
                        {(OUTPUT_PADDING/2){result_r[OPERAND_WIDTH_OUT - 1]}}, result_r};
                    for (i = 1; i<(STAGES-CALCULATION_STAGES); i = i+1) begin
                        tdata[i] <= tdata[i-1];
                    end
                    m_axis_dout_tdata <= tdata[STAGES - CALCULATION_STAGES - 1];
                end
                else begin
                     m_axis_dout_tdata <= {{(OUTPUT_PADDING/2){result_i[OPERAND_WIDTH_OUT - 1]}}, result_i,
                         {(OUTPUT_PADDING/2){result_r[OPERAND_WIDTH_OUT - 1]}}, result_r};
                end
            end
        end
    end
endmodule