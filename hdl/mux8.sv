
// 74HC251

module mux8 (
    input logic [7:0] i_Inputs,
    input logic [2:0] i_Control,
    output logic o_Output
    // TODO: output enable?
    // output o_OutputComplement,
);

assign o_Output = i_Inputs[i_Control];

endmodule
