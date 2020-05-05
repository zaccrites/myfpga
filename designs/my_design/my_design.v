
// module my_design (
//     input i_Clock,
//     input i_Reset,
//     input i_Data,
//     output [3:0] o_DataFF,
//     output o_DataPassthrough,
//     output o_DataOp
// );

// reg [3:0] r_Data;
// assign o_DataFF = r_Data;

// always @ (posedge i_Clock) begin
//     r_Data[0] <= i_Data;
//     r_Data[1] <= ~i_Data;
//     r_Data[2] <= i_Data & ~i_Reset;
//     r_Data[3] <= r_Data[2];
// end

// assign o_DataPassthrough = i_Data;
// assign o_DataOp = ~i_Data;

// endmodule


module my_design (
    input i_Clock,
    input i_Sel,
    input i_Data,
    output o_Data
);

reg r_Data;
always @ (posedge i_Clock) begin
    r_Data <= i_Sel ? i_Data : ~r_Data;
    // r_Data <= ~i_Data;
end

assign o_Data = r_Data;

endmodule


