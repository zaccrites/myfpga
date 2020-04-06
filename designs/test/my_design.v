
module my_design (
    input i_Clock,

    input i_WriteEnable,
    input i_DataIn0,
    input i_DataIn1,
    input i_DataIn2,
    input i_DataIn3,

    input i_Address0,
    input i_Address1,
    input i_Address2,
    input i_Address3,

    output o_Output0,
    output o_Output1,
    output o_Output2,
    output o_Output3,
);


reg [3:0] r_Memory [16];

wire [3:0] w_Address;
assign w_Address = {
    i_Address3,
    i_Address2,
    i_Address1,
    i_Address0
};

always @ (posedge i_Clock) begin
    o_Output3 <= r_Memory[w_Address][3];
    o_Output2 <= r_Memory[w_Address][2];
    o_Output1 <= r_Memory[w_Address][1];
    o_Output0 <= r_Memory[w_Address][0];

    if (i_WriteEnable) begin
        r_Memory[w_Address][3] <= i_DataIn3;
        r_Memory[w_Address][2] <= i_DataIn2;
        r_Memory[w_Address][1] <= i_DataIn1;
        r_Memory[w_Address][0] <= i_DataIn0;
    end

end

endmodule


