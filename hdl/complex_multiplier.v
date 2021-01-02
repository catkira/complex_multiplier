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
      parameter int STAGES `VL_RD = 3,
      parameter bit BLOCKING `VL_RD = 0,
      parameter bit TRUNCATE `VL_RD = 1)
    (   
        input wire             clk, rst,
        // slave a
        input signed            [INPUT_WIDTH_A-1:0] s_axis_a_tdata,
        output wire                           s_axis_a_tready,
        input wire                            s_axis_a_tvalid,
        // slave b
        input signed            [INPUT_WIDTH_B-1:0] s_axis_b_tdata,
        output wire                           s_axis_b_tready,
        input wire                            s_axis_b_tvalid,
        // master output
        output reg signed		  [OUTPUT_WIDTH-1:0] m_axis_tdata,
        output wire                          m_axis_tvalid,
        input wire                           m_axis_tready
        );
    // p = a*b = p_r + jp_i = (a_r*b_r - a_i*b_i) + j(a_r*b_i + a_i*b_r)
    // stage1: calculate a_r*b_r, a_i*b_i, a_r*b_i, a_i*b_r
    // stage2: calculate p_r and p_i

    reg signed [OUTPUT_WIDTH/2-1:0] ar_br, ai_bi, ar_bi, ai_br;
    reg        [STAGES:0]                    tvalid  ;
    reg        [OUTPUT_WIDTH-1:0]              tdata [STAGES-2:0];

    wire signed [INPUT_WIDTH_A/2-1:0] a_r;
    wire signed [INPUT_WIDTH_A/2-1:0] a_i;
    wire signed [INPUT_WIDTH_B/2-1:0] b_r;
    wire signed [INPUT_WIDTH_B/2-1:0] b_i;
    assign a_i = s_axis_a_tdata[INPUT_WIDTH_A-1:INPUT_WIDTH_A/2];
    assign a_r = s_axis_a_tdata[INPUT_WIDTH_A/2-1:0];
    assign b_i = s_axis_b_tdata[INPUT_WIDTH_B-1:INPUT_WIDTH_B/2];
    assign b_r = s_axis_b_tdata[INPUT_WIDTH_B/2-1:0];
    assign s_axis_a_tready = 1;
    assign s_axis_b_tready = 1;
    
    localparam TRUNC_BITS = INPUT_WIDTH_A + INPUT_WIDTH_B - OUTPUT_WIDTH;

    integer i;
    always @(posedge clk) begin
        if (rst) begin
            m_axis_tdata <= {(OUTPUT_WIDTH){1'b0}};
            m_axis_tvalid <= 0;
            tvalid <= {{(STAGES){1'b0}}};
            for (i=0;i<(STAGES-1);i=i+1)
                tdata[i] <= {OUTPUT_WIDTH{1'b0}};
            ai_bi <= {OUTPUT_WIDTH{1'b0}};
            ai_br <= {OUTPUT_WIDTH{1'b0}};
            ar_bi <= {OUTPUT_WIDTH{1'b0}};
            ar_br <= {OUTPUT_WIDTH{1'b0}};
        end
        else begin
            if (BLOCKING == 1 && m_axis_tready == 0) begin
                m_axis_tvalid <= 0;
                m_axis_tdata <= {(OUTPUT_WIDTH){1'b0}};
            end
            else begin
                if (TRUNC_BITS == 0) begin
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
                
                // propagate valid bit through pipeline
                tvalid[0] <= s_axis_a_tvalid & s_axis_b_tvalid;
                for (i = 1; i<(STAGES); i = i+1) begin
                    tvalid[i] <= tvalid[i-1];
                end
                m_axis_tvalid <= tvalid[STAGES-2];
                
                // propagate data through pipeline, 1 cycle is already used for calculation
                if (STAGES > 2) begin
                    tdata[0] <= {{ar_bi + ai_br},{ar_br - ai_bi}};
                    for (i = 1; i<(STAGES-2); i = i+1) begin
                        tdata[i] <= tdata[i-1];
                    end
                    m_axis_tdata <= tdata[STAGES-3];
                end
                else begin
                    m_axis_tdata <= {{ar_bi + ai_br},{ar_br - ai_bi}};
                end
            end
        end
    end
endmodule