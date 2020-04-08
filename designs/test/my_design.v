
module my_design (
    input i_Clock,
    // input i_Reset,
    input [3:0] i_Input,
    output [1:0] o_Output,
    output o_OutputFF
);

reg r_Storage;

always @* begin
    o_Output[0] = i_Input[0] & i_Input[1];
    o_Output[1] = i_Input[2] | i_Input[3];
end

always @ (posedge i_Clock) begin
    r_Storage <= ~i_Input[0] & i_Input[1];
end

assign o_OutputFF = ~r_Storage;


// always @ (posedge i_Clock) begin
//     if (i_Reset) begin
//         o_Output <= 0;
//     end
//     else begin
//         o_Output <= o_Output + i_Amount;
//     end
// end


endmodule
