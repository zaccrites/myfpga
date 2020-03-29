
// 74HC595

module shift_register8 (
    input logic i_ShiftClock,
    input logic i_LatchClock,
    input logic i_Reset,
    input logic i_DataIn,
    output logic o_DataOut,
    output logic [7:0] o_Outputs
);

logic [7:0] r_InternalData;


always_ff @ (posedge i_LatchClock) begin
    o_Outputs <= r_InternalData;
end


always_ff @ (posedge i_ShiftClock or negedge i_Reset) begin
    if (~i_Reset) begin
        r_InternalData <= 0;
    end
    else begin
        o_DataOut <= r_InternalData[7];
        r_InternalData[7:1] <= r_InternalData[6:0];
        r_InternalData[0] <= i_DataIn;
    end
end

endmodule
