
use rand::prelude::*;


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

    let num_clusters = 5;
    let points_per_cluster = 30;
    let cluster_radius = 4.0;
    let total_radius = 30.0;

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


pub fn anneal() {
    let mut rng = rand::thread_rng();

    let mut current_state = create_constellation();
    let mut current_energy = calc_energy(&current_state);
    let initial_energy = current_energy;

    let max_steps = 80000;
    for step in 1..=max_steps {
        let t = calc_temperature(step, max_steps);

        // TODO: More efficient copying?
        let mut new_state = current_state.clone();
        move_state(&mut new_state);
        let new_energy = calc_energy(&new_state);

        let r: f64 = rng.gen();
        if acceptance_probability(current_energy, new_energy, t) > r {
            current_state = new_state;
            current_energy = new_energy;
            println!("energy = {:?}", current_energy);
        }
    }

    println!("Initial Energy: {:?}", initial_energy);
    println!("Final Energy:   {:?}", current_energy);
}


fn calc_temperature(step: i32, max_steps: i32) -> f64 {
    let max_temp = 30000.0f64;
    let min_temp = 1.0f64;
    let factor = -(max_temp / min_temp).ln();

    let step = step as f64;
    let max_steps = max_steps as f64;
    max_temp * (factor * step / max_steps).exp()
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
