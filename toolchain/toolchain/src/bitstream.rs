

// use crate::routing::{RoutingConfiguration, DeviceTopology};
use crate::routing::{RoutingConfiguration};


#[derive(Debug)]
pub enum BitstreamError {

}



pub struct BitstreamConfiguration {

    // TODO: Use a method to generate bytes or implement IntoIterator<u8> or whatever it's called

    // Don't forget to padd the start with enough bits to make a full byte
    // so that they get shifted out at the end.
    // Is it better to make a list of bool and convert that to u8 later?

    // Don't forget that the first bit in is the final configuration bit

    // Adapting an iterator of bool to iterator of u8 is easy, but may not be
    // the most efficient.
    // What about a trait for each configuration field with an associated constant
    // for its length in bits? That would make some of the work doable at compile time.
    // https://doc.rust-lang.org/edition-guide/rust-2018/trait-system/associated-constants.html

}


pub fn generate_bitstream(routing_config: &RoutingConfiguration) -> Result<BitstreamConfiguration, BitstreamError> {




    let config = BitstreamConfiguration {};
    Ok(config)
}
