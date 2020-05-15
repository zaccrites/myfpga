

module switch_block(
    input logic i_ConfigClock,
    input logic i_ConfigShiftInput,
    output logic o_ConfigShiftOutput,

    input logic [3:0] i_SideInputs [4],
    output logic [3:0] o_SideOutputs [4],

    input logic i_CornerInputs [4]

);

integer i;
// integer j;

// 3 bits per mux, 4 muxes per side, 4 sides = 48 bits
logic [47:0] r_OutputMuxConfig;
always_ff @ (posedge i_ConfigClock) begin
    r_OutputMuxConfig[0] <= i_ConfigShiftInput;
    for (i = 1; i <= 47; i++) r_OutputMuxConfig[i] <= r_OutputMuxConfig[i - 1];
    o_ConfigShiftOutput <= r_OutputMuxConfig[47];
end


always_comb begin

    // Output 0 for same side
    // case (r_OutputMuxConfig[2:0])
    //     0 : o_SideOutputs[0][0] = i_CornerInputs[`NORTHWEST];
    //     1 : o_SideOutputs[0][0] = i_SideInputs[`NORTH][0];
    //     2 : o_SideOutputs[0][0] = i_CornerInputs[`NORTHEAST];
    //     3 : o_SideOutputs[0][0] = i_SideInputs[`EAST][0];
    //     4 : o_SideOutputs[0][0] = i_CornerInputs[`SOUTHEAST];
    //     5 : o_SideOutputs[0][0] = i_SideInputs[`SOUTH][0];
    //     6 : o_SideOutputs[0][0] = i_CornerInputs[`SOUTHWEST];
    //     7 : o_SideOutputs[0][0] = i_SideInputs[`WEST][0];
    // endcase

    case (r_OutputMuxConfig[2:0])
        0 : o_SideOutputs[`NORTH][0] = i_CornerInputs[`NORTHWEST];
        1 : o_SideOutputs[`NORTH][0] = 0;
        2 : o_SideOutputs[`NORTH][0] = i_CornerInputs[`NORTHEAST];
        3 : o_SideOutputs[`NORTH][0] = i_SideInputs[`EAST][0];
        4 : o_SideOutputs[`NORTH][0] = i_CornerInputs[`SOUTHEAST];
        5 : o_SideOutputs[`NORTH][0] = i_SideInputs[`SOUTH][0];
        6 : o_SideOutputs[`NORTH][0] = i_CornerInputs[`SOUTHWEST];
        7 : o_SideOutputs[`NORTH][0] = i_SideInputs[`WEST][0];
    endcase

end


endmodule
