
module my_design (
    input i_Clock,
    input i_Reset,
    output [3:0] o_Data
);

always @ (posedge i_Clock) begin
    o_Data <= i_Reset ? 0 : (o_Data + 1);
end

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