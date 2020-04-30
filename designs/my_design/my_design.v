
// module my_design (
//     input i_Clock,
//     input i_Reset,
//     input [3:0] i_Incr,
//     output [3:0] o_Data
// );

// reg [3:0] r_Data;

// always @ (posedge i_Clock) begin
//     if (i_Reset) begin
//         r_Data <= 0;
//     end
//     else begin
//         r_Data <= r_Data + i_Incr;
//     end
// end

// assign o_Data = r_Data;

// endmodule

module my_design (
    input i_Clock,
    input i_Reset,
    input i_Data,
    output o_DataFF,
    output o_DataPassthrough,
    output o_DataOp
);

reg r_Data;
assign o_DataFF = r_Data;

always @ (posedge i_Clock) begin
    r_Data <= i_Data;
end

assign o_DataPassthrough = i_Data;
assign o_DataOp = ~i_Data;

endmodule



// module my_design (
//     input i_Clock,
//     // input i_Reset,
//     input i_Data1,
//     input i_Data2,
//     output o_Data1,
//     output o_Data2,
//     output o_Data3,
//     output o_Data4,
//     output o_Data5,
//     output o_Data6
// );

// // reg [2:0] r_Data;

// always @ (posedge i_Clock) begin
//     // if (i_Reset) begin

//     // end
//     // else begin
//         // r_Data[0] <= i_Data;
//         // r_Data[1] <= ~r_Data[0];
//         // r_Data[2] <= r_Data[1];
//     // end

//     o_Data1 <= i_Data1;
//     o_Data2 <= ~i_Data1;

//     o_Data6 <= ~o_Data6;

// end

// assign o_Data3 = i_Data2;
// assign o_Data4 = ~i_Data2;

// assign o_Data5 = o_Data4 & o_Data2;

// endmodule
