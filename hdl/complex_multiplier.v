`timescale 1ns/1ps

`ifdef VERILATOR  // make parameter readable from VPI
  `define VL_RD /*verilator public_flat_rd*/
`else
  `define VL_RD
`endif

module complex_multiplier
    #(parameter int INPUT_WIDTH_A `VL_RD = 16,
      parameter int INPUT_WIDTH_B `VL_RD = 16,
      parameter int OUTPUT_WIDTH `VL_RD = 32,
      parameter TRUNCATE `VL_RD = 1)
    (   
        input wire             clk, rst,
        // slave a
        input             [INPUT_WIDTH_A-1:0] s_axis_a_tdata,
        output wire                           s_axis_a_tready,
        input wire                            s_axis_a_tvalid,
        // slave b
        input             [INPUT_WIDTH_B-1:0] s_axis_b_tdata,
        output wire                           s_axis_b_tready,
        input wire                            s_axis_b_tvalid,
        // master output
        output reg 		  [OUTPUT_WIDTH-1:0] m_axis_tdata,
        output wire                          m_axis_tvalid,
        input wire                           m_axis_tready
        );
    // p = a*b = p_r + jp_i = (a_r*b_r - a_i*b_i) + j(a_r*b_i + a_i*b_r)
    // stage1: calculate a_r*b_r, a_i*b_i, a_r*b_i, a_i*b_r
    // stage2: calculate p_r and p_i

    reg [OUTPUT_WIDTH/2-1:0] ar_br, ai_bi, ar_bi, ai_br;

    wire [INPUT_WIDTH_A/2-1:0] a_r;
    wire [INPUT_WIDTH_A/2-1:0] a_i;
    wire [INPUT_WIDTH_B/2-1:0] b_r;
    wire [INPUT_WIDTH_B/2-1:0] b_i;
    assign a_i = s_axis_a_tdata[INPUT_WIDTH_A-1:INPUT_WIDTH_A/2];
    assign a_r = s_axis_a_tdata[INPUT_WIDTH_A/2-1:0];
    assign b_i = s_axis_b_tdata[INPUT_WIDTH_B-1:INPUT_WIDTH_B/2];
    assign b_r = s_axis_b_tdata[INPUT_WIDTH_B/2-1:0];
    assign s_axis_a_tready = 1;
    assign s_axis_b_tready = 1;
    assign m_axis_tvalid = 1;
    
    localparam TRUNC_BITS = INPUT_WIDTH_A + INPUT_WIDTH_B - OUTPUT_WIDTH;

    always @(posedge clk) begin
        if (~rst) begin
            m_axis_tdata <= {(OUTPUT_WIDTH){1'b0}};
        end
        else begin
            if (TRUNC_BITS != 0) begin
            // no rounding or truncation needed
                ar_br <= a_r * b_r;
                ai_bi <= a_i * b_i;
                ar_bi <= a_r * b_i;
                ai_br <= a_i * b_r;
            end
            else begin
                if (TRUNCATE == 1) begin
                    ar_br <= ((a_r * b_r)>>TRUNC_BITS);
                    ai_bi <= ((a_i * b_i)>>TRUNC_BITS);
                    ar_bi <= ((a_r * b_i)>>TRUNC_BITS);
                    ai_br <= ((a_i * b_r)>>TRUNC_BITS);                 
                end
                else begin
                // TODO: implement rounding
                end
            end
            m_axis_tdata <= {{ar_br - ai_bi},{ar_bi + ai_br}};
        end
    end
endmodule