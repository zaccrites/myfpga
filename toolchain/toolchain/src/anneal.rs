
use rand::prelude::*;


use std::thread;
use std::sync::{mpsc, Arc, RwLock};


struct WorkerResult { energy: f64, state: Vec<Point> }  // TODO: diff only


#[derive(Debug, Clone, Copy)]
struct JobData {
    previous_energy: f64,
    temperature: f64,
}


struct Worker {
    job_sender: mpsc::Sender<Option<JobData>>,
}

impl Worker {
    fn send_job(&self, job: JobData) {
        self.job_sender.send(Some(job)).unwrap();
    }

    fn stop(&self) {
        self.job_sender.send(None).unwrap();
    }

    // TODO: Use bounded sync_channel instead?
    fn new(state: Arc<RwLock<Vec<Point>>>, results_sender: mpsc::Sender<Option<WorkerResult>>) -> Self {
        let (job_sender, job_receiver) = mpsc::channel::<Option<JobData>>();

        thread::spawn(move || {
            let mut rng = rand::thread_rng();
            while let Some(job_data) = job_receiver.recv().unwrap() {

                // Create a local copy of the state to mutate in this thread.
                let mut state = state.read().unwrap().clone();

                // In this case I think the channel overhead is just too much
                // compared to the work done by each thread.
                move_state(&mut state);
                let new_energy = calc_energy(&state);

                // Simulate an expensive operation to prevent threading
                // overhead from overshadowing operation runtime.
                thread::sleep(std::time::Duration::from_millis(100));

                let accept_prob = acceptance_probability(job_data.previous_energy, new_energy, job_data.temperature);
                let job_result = if accept_prob > rng.gen() {
                    Some(WorkerResult {
                        energy: new_energy,
                        state,
                    })
                }
                else {
                    None
                };

                if results_sender.send(job_result).is_err() {
                    println!("main thread hung up");
                    break;
                }
            }
        });

        Self {
            job_sender,
        }
    }
}


struct Annealer {
    state: Arc<RwLock<Vec<Point>>>,
    workers: Vec<Worker>,
    results_receiver: mpsc::Receiver<Option<WorkerResult>>,
}

impl Annealer {

    fn new(num_threads: usize, state: Vec<Point>) -> Self {
        let state = Arc::new(RwLock::new(state));
        let (results_sender, results_receiver) = mpsc::channel();

        let mut workers = Vec::new();
        for _ in 0..num_threads {
            let state = Arc::clone(&state);
            workers.push(Worker::new(state, results_sender.clone()));
        }

        Self {
            state,
            workers,
            results_receiver,
        }
    }

    fn anneal(&mut self, max_steps: i32) -> Vec<Point> {
        let mut previous_energy = calc_energy(&*self.state.read().unwrap());

        assert!(max_steps > 1);
        for step in 1..=max_steps {
            let job_data = JobData {
                previous_energy,
                temperature: self.calc_temperature(step, max_steps),
            };

            for worker in &self.workers {
                worker.send_job(job_data);
            }

            // Wait for results to come in
            let mut results = Vec::new();
            while results.len() < self.workers.len() {
                let result = self.results_receiver.recv().unwrap();
                results.push(result);
            }

            // Filter out None results, then take the one with the least energy.
            let mut results: Vec<_> = results.iter().flatten().collect();
            results.sort_by(|a, b| a.energy.partial_cmp(&b.energy).unwrap());
            if let Some(result) = results.get(0) {
                *self.state.write().unwrap() = result.state.clone();
                previous_energy = result.energy;
            }

            if step % 5000 == 0 {
                println!("step[{}] | energy = {:?}", step, previous_energy);
            }

        }

        // Terminate the threads
        for worker in &self.workers {
            worker.stop();
        }

        self.state.read().unwrap().clone()
    }

    fn calc_temperature(&self, step: i32, max_steps: i32) -> f64 {
        let max_temp = 30000.0f64;
        let min_temp = 1.0f64;
        let factor = -(max_temp / min_temp).ln();

        let step = step as f64;
        let max_steps = max_steps as f64;
        max_temp * (factor * step / max_steps).exp()
    }

}


#[derive(Debug, Copy, Clone)]
struct Point {
    x: f64,
    y: f64,
}

impl Point {
    fn new(x: f64, y: f64) -> Point {
        Point {
            x,
            y,
        }
    }

    fn dist(&self, other: &Point) -> f64 {
        let dx = self.x - other.x;
        let dy = self.y - other.y;
        (dx * dx + dy * dy).sqrt()
    }
}


#[derive(Debug, Copy, Clone)]
struct Circle {
    center: Point,
    radius: f64,
}

impl Circle {
    fn new(center: Point, radius: f64) -> Circle {
        Circle {
            center,
            radius,
        }
    }

    fn random_point_inside(&self) -> Point {
        let mut rng = rand::thread_rng();
        let radius = self.radius * rng.gen::<f64>();
        let angle = 2.0 * std::f64::consts::PI * rng.gen::<f64>();
        let x = self.center.x + radius * angle.cos();
        let y = self.center.y + radius * angle.sin();
        Point::new(x, y)
    }
}


fn create_constellation() -> Vec<Point> {
    let mut points = Vec::new();

    // let num_clusters = 100;
    // let points_per_cluster = 3000;
    // let cluster_radius = 500.0;
    // let total_radius = 100000.0;

    let num_clusters = 100;
    let points_per_cluster = 3000;
    let cluster_radius = 500.0;
    let total_radius = 100000.0;

    let origin = Point::new(0.0, 0.0);
    let total_circle = Circle::new(origin, total_radius);

    for i in 0..num_clusters {
        let cluster_center = total_circle.random_point_inside();
        let cluster_circle = Circle::new(cluster_center, cluster_radius);
        println!("Cluster {} at {:?}", i, cluster_center);

        points.extend(
            (0..points_per_cluster)
            .map(|_| cluster_circle.random_point_inside())
        );
    }

    let mut rng = rand::thread_rng();
    points.shuffle(&mut rng);
    points
}


pub fn anneal(num_threads: usize) {
    // let mut rng = rand::thread_rng();

    let initial_state = create_constellation();
    let initial_energy = calc_energy(&initial_state);
    let mut annealer = Annealer::new(num_threads, initial_state);

    let max_steps = 500;
    // let max_steps = 50000;

    let start = std::time::Instant::now();
    let end_state = annealer.anneal(max_steps);
    let end_energy = calc_energy(&end_state);
    let end = std::time::Instant::now();
    let duration = end.duration_since(start);

    println!("Initial Energy: {:?}", initial_energy);
    println!("Final Energy:   {:?} ({:.1}%)", end_energy, end_energy / initial_energy * 100.0);
    println!("Duration: {:.3} seconds", duration.as_secs_f64());
}


fn calc_energy(state: &[Point]) -> f64 {
    // "Energy" is the total distance between all points on the path
    let next_point = state.iter().skip(1);
    state.iter().zip(next_point).fold(0.0, |acc, (p1, p2)| acc + p1.dist(p2))
}


fn move_state(state: &mut Vec<Point>) {
    let mut rng = rand::thread_rng();
    let mut get_num = || rng.gen_range(0, state.len());
    let a: usize = get_num();
    let b: usize = std::iter::repeat_with(get_num).find(|&b| b != a).unwrap();
    state.swap(a, b);
}


fn acceptance_probability(current_energy: f64, new_energy: f64, temperature: f64) -> f64 {
    // https://en.wikipedia.org/wiki/Simulated_annealing#Acceptance_probabilities_2
    if new_energy < current_energy {
        1.0
    }
    else {
        (-(new_energy - current_energy) as f64 / temperature).exp()
    }
}
