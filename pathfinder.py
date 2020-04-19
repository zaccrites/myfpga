
import heapq

import networkx as nx


class PriorityQueue:

    def __init__(self):
        self.items = []

    def __bool__(self):
        return bool(self.items)

    def __len__(self):
        return len(self.items)

    def __contains__(self, item):
        for _priority, this_item in self.items:
            if this_item is item:
                return True
        return False

    def push(self, item, *, priority):
        heapq.heappush(self.items, (priority, item))

    def pop(self):
        _priority, item = heapq.heappop(self.items)
        return item

    def __repr__(self):
        return f'{self.__class__.__name__}({self.items!r})'


class Router:
    """Implement PathFinder algorithm."""

    def __init__(self):
        pass

    def signal_router(self):
        pass


def pathfinder(graph, nets):

    # pn = {node: 1 for node in graph}
    hn = {node: 0 for node in graph}
    bn = {node: 1 for node in graph}
    def cn(node):
        return (bn[node] + hn[node]) * pn[node]

    def edge_weight(start, end, attrs):
        return cn(end) + attrs['path_cost']

    # We assume this is true at first to generate initial routes
    shared_resources_exist = True
    routes = {}

    while shared_resources_exist:
        pn = {node: 1 for node in graph}

        for source, sinks in nets.items():
            RTi = {source}

            for sink in sinks:
                PQ = PriorityQueue()
                for node in RTi:
                    PQ.push(node, priority=0)

                # while sink tij not found
                while True:
                    node = PQ.pop()
                    if node == sink:
                        # Strip off the source and sink nodes from the path.
                        path = nx.dijkstra_path(graph, source, sink, weight=edge_weight)[1:-1]
                        for path_node in path:
                            RTi.add(path_node)
                            pn[path_node] += 1

                        routes[source] = path
                        break

                    else:
                        for _start, end, path_cost in graph.out_edges(node, data='path_cost'):
                            cost = cn(node) + path_cost
                            PQ.push(end, priority=cost)

        for key, value in pn.items():
            hn[key] += value

        # Each value starts at 1, and 1 is added for each user.
        shared_resources_exist = any(value > 2 for value in pn.values())

    return routes


def main():
    graph = nx.DiGraph()

    nets = {
        'S1': {'D1'},
        'S2': {'D2'},
        'S3': {'D3'},
    }

    # Figure 1 graph
    # ------------------------------------------
    graph.add_edge('S1', 'A', path_cost=2)
    graph.add_edge('S1', 'B', path_cost=1)

    graph.add_edge('S2', 'A', path_cost=3)
    graph.add_edge('S2', 'B', path_cost=1)
    graph.add_edge('S2', 'C', path_cost=4)

    graph.add_edge('S3', 'B', path_cost=1)
    graph.add_edge('S3', 'C', path_cost=3)

    graph.add_edge('A', 'D1', path_cost=2)
    graph.add_edge('A', 'D2', path_cost=3)

    graph.add_edge('B', 'D1', path_cost=1)
    graph.add_edge('B', 'D2', path_cost=1)
    graph.add_edge('B', 'D3', path_cost=1)

    graph.add_edge('C', 'D2', path_cost=4)
    graph.add_edge('C', 'D3', path_cost=3)
    # ------------------------------------------


    # # Figure 2 graph
    # # ------------------------------------------
    # graph.add_edge('S1', 'A', path_cost=2)
    # graph.add_edge('S1', 'B', path_cost=1)
    # graph.add_edge('S2', 'B', path_cost=2)
    # graph.add_edge('S2', 'C', path_cost=1)
    # graph.add_edge('S3', 'C', path_cost=1)

    # graph.add_edge('A', 'D1', path_cost=2)
    # graph.add_edge('B', 'D1', path_cost=1)
    # graph.add_edge('B', 'D2', path_cost=2)
    # graph.add_edge('C', 'D2', path_cost=1)
    # graph.add_edge('C', 'D3', path_cost=1)
    # # ------------------------------------------

    routes = pathfinder(graph, nets)
    print(routes)


if __name__ == '__main__':
    main()
