
module logic_cell(
    input logic i_ConfigClock,
    input logic i_LogicClock,

    input logic i_ConfigActive,
    input logic i_ConfigShiftInput,
    output logic o_ConfigShiftOutput,

    input logic [3:0] i_LookupTableInputs,
    output logic o_Output
);

integer i;

logic [15:0] r_LookupTableMask;
logic r_FlipFlopBypass;
logic r_InputClockPolarity;

always_ff @ (posedge i_ConfigClock) begin
    r_LookupTableMask[0] <= i_ConfigShiftInput;
    for (i = 1; i <= 15; i++) begin
        r_LookupTableMask[i] <= r_LookupTableMask[i - 1];
    end
    r_FlipFlopBypass <= r_LookupTableMask[15];
    r_InputClockPolarity <= r_FlipFlopBypass;
    o_ConfigShiftOutput <= r_InputClockPolarity;
end

logic w_LogicClock;
assign w_LogicClock = r_InputClockPolarity ? ~i_LogicClock : i_LogicClock;

logic w_LookupTableOutput;
assign w_LookupTableOutput = r_LookupTableMask[i_LookupTableInputs];

logic r_FlipFlopOutput;
always_ff @ (posedge w_LogicClock or negedge i_ConfigActive) begin
    if (~i_ConfigActive)
        r_FlipFlopOutput <= 0;
    else
        r_FlipFlopOutput <= w_LookupTableOutput;
end

assign o_Output = r_FlipFlopBypass ? w_LookupTableOutput : r_FlipFlopOutput;


endmodule
