
// use rand::prelude::*;


// use std::thread;
// use std::sync::{mpsc, Arc, RwLock};


// struct JobData {
//     previous_result: PathfinderResult,
//     temperature: f64,
// }



// struct WorkerResult {
//     config: RoutingConfiguration,
//     result: PathfinderResult,
// }


// struct Worker {

// }

// impl Worker {
//     // // TODO: Use bounded sync_channel instead?
//     // fn new(config: Arc<RwLock<RoutingConfiguration>>, results_sender: mpsc::Sender<WorkerResult>) -> Self {
//     //     let (job_sender, job_receiver) = mpsc::channel::<Option<JobData>>();
//     //     thread::spawn(move || {
//     //         while let Some(job_data) = job_receiver.recv().unwrap() {
//     //             let mut config = config.read().unwrap().clone();

//     //         }
//     //     });

//     // }
// }

// fn mutate_config(config: &mut RoutingConfiguration) {
//     let mut rng = rand::thread_rng();
//     // let move_logic_cell = rng::gen::<f64>




// }




// use crate::routing::topology::{LogicCellCoordinates, IoBlockCoordinates, DeviceTopology};





// // type MutateFunc = fn(&mut RoutingConfiguration);
// // type EnergyFunc = fn(&RoutingConfiguration) -> PathfinderResult;

// // TODO: convert pathfinder result to an energy level which I can take the difference of?
// // Need to subtract in acceptance probability somehow

// // Maybe implement a trait for Energy which requires partial ord and has a function
// // to convert to a plain f64? I guess it doesn't really HAVE to be PartialOrd if I can convert o a float.
// // Remember that nonroutable always has greater energy. Maybe that has positive energy and
// // routable has negative, if that's allowed.

// use crate::routing::RoutingConfiguration;


// pub struct Annealer<E: PartialOrd> {
//     mutate_func: MutateFunc,  // return energy?
//     energy_func: EnergyFunc<E>,

//     best_energy: Option<E>,  // todo
// }

// impl<E: PartialOrd> Annealer<E> {

//     pub fn new(initial_state: RoutingConfiguration, mutate_func: MutateFunc, energy_func: EnergyFunc<E>) -> Self
//     {
//         Annealer {
//             mutate_func,
//             energy_func,
//             best_energy: None,
//         }
//     }

//     pub fn anneal(&self) -> (RoutingConfiguration, PathfinderResult) {
//         // TODO: Return Result<> with some error as needed

//         // Returns the winning routing config and the score/congestion that went with it.



//     }

// }





// use crate::pathfinder::PathfinderResult;
// // fn test() {
// //     fn mf (state: &mut State) {}
// //     // let ef = |state| 0.0;
// //     fn ef (state: &State) -> PathfinderResult { PathfinderResult::NotRouted {congestion: 10} }
// //     let x = Annealer2::new(State, mf, ef);
// // }


// fn acceptance_probability2(current_result: PathfinderResult, new_result: PathfinderResult, temperature: f64) -> f64 {
//     // https://en.wikipedia.org/wiki/Simulated_annealing#Acceptance_probabilities_2

//     // FUTURE: Tune acceptance parameters for routed vs not routed phases

//     match (current_result, new_result) {
//         (PathfinderResult::NotRouted {..}, PathfinderResult::Routed {..}) => 1.0,

//         // This formulation will never accept a move which makes the placement
//         // unroutable. I don't know if that will lead to getting trapped in the
//         // first routable configuration, or if that's a problem.
//         (PathfinderResult::Routed {..}, PathfinderResult::NotRouted {..}) => 0.0,

//         (PathfinderResult::NotRouted {congestion: current_congestion}, PathfinderResult::NotRouted {congestion: new_congestion}) =>
//         if new_congestion < current_congestion {
//             1.0
//         }
//         else {
//             // Minimize congestion
//             let congestion_diff = (new_congestion - current_congestion) as f64;
//             (-congestion_diff / temperature).exp()
//         },

//         (PathfinderResult::Routed {score: current_score, ..}, PathfinderResult::Routed {score: new_score, ..}) =>
//         if new_score > current_score {
//             1.0
//         }
//         else {
//             // Maximize score
//             let score_diff = current_score - new_score;
//             (-score_diff / temperature).exp()
//         },
//     }
// }




