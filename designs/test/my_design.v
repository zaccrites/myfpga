
module my_design (
    input i_Clock,
    input i_Reset,
    input i_Enable,
    output o_Output0,
    output o_Output1,
    output o_Output2,
    output o_Output3,
);


reg [3:0] r_Data;

always @ (posedge i_Clock) begin
    if (i_Reset) begin
        r_Data <= 0;
    end
    else
    if (i_Enable) begin
        r_Data <= r_Data + 1;
    end
end

assign o_Output3 = r_Data[3];
assign o_Output2 = r_Data[2];
assign o_Output1 = r_Data[1];
assign o_Output0 = r_Data[0];

endmodule


// module my_design (
//     input i_Clock,
//     input i_DataIn,
//     output o_Output0,
//     output o_Output1,
//     output o_Output2,
//     output o_Output3,
// );



// always @ (posedge i_Clock) begin
//     o_Output0 <= i_DataIn;
//     o_Output1 <= o_Output0;
//     o_Output2 <= o_Output1;
//     o_Output3 <= o_Output2;
// end

// // assign o_Output3 = r_Data[3];
// // assign o_Output2 = r_Data[2];
// // assign o_Output1 = r_Data[1];
// // assign o_Output0 = r_Data[0];



// endmodule
