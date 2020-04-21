"""Implement the PathFinder negotiated congestion router."""

import heapq

import networkx as nx


class PriorityQueue:

    def __init__(self, items=None):
        self.items = []
        self._itemset = set()
        self._counter = 0

        if items is not None:
            for item in items:
                self.push(item, priority=0)

    def __bool__(self):
        return bool(self.items)

    def __len__(self):
        return len(self.items)

    def __contains__(self, item):
        return item in self._itemset

    def push(self, item, *, priority):
        heapq.heappush(self.items, (priority, self._counter, item))
        self._itemset.add(item)
        self._counter += 1

    def pop(self):
        _priority, _counter, item = heapq.heappop(self.items)
        self._itemset.remove(item)
        return item

    def __repr__(self):
        return f'{self.__class__.__name__}({self.items!r})'


def route(graph, nets):  # noqa: C901
    historical_use_cost = {node: 0 for node in graph}
    base_cost = {node: 1 for node in graph}

    # Note that this only computes negotiated congestion cost.
    # A future enhancement can add delay cost as well for a complete
    # PathFinder implementation.
    def cost_function(node):
        return (base_cost[node] + historical_use_cost[node]) * present_use_cost[node]

    def edge_weight(start, end, attrs):
        return cost_function(end) + attrs['cost']

    routes = {}

    shared_resources_exist = True
    while shared_resources_exist:
        present_use_cost = {node: 1 for node in graph}

        # TODO: Improve perfomrance by only re-routing signals which
        # have shared resources.

        for source, sinks in nets.items():
            # We begin by looking at the source node.
            # For each sink connected to the source, we consider a "routing
            # tree" (which is really just a set) of nodes in the net connecting
            # the source and sinks.
            routing_tree = {source}
            for sink in sinks:
                # We have to find a way to connect each sink to the routing tree.
                queue = PriorityQueue(routing_tree)
                seen_nodes = set()
                while True:
                    # Look at the most promising (lowest cost) node in the queue.
                    node = queue.pop()
                    seen_nodes.add(node)
                    # If the node is the sink we're looking for,
                    # we trace back the path to the source and add each node
                    # to the routing tree.
                    if node == sink:
                        path = nx.dijkstra_path(graph, source, sink, weight=edge_weight)
                        for path_node in path[1:-1]:
                            routing_tree.add(path_node)
                        break
                    else:
                        # If it's not the sink we're looking for,
                        # then we add each node that this node can connect to.
                        # They are added to the priority queue so that the next
                        # node we look at is the lowest cost potential path
                        # to the sink.
                        for _start, end, path_cost in graph.out_edges(node, data='cost'):
                            if end not in queue and end not in seen_nodes:
                                queue.push(end, priority=cost_function(node) + path_cost)

            # Increment the present use cost for all of the nodes that
            # we're using.
            for node in routing_tree:
                present_use_cost[node] += 1
            routes[source] = routing_tree

        # The starting value is 1, and is increased by 1 for each user of the resource.
        #  present_use_cost = 1 : unused
        #  present_use_cost = 2 : exclusively used by one net
        #  present_use_cost > 2 : shared by multiple nets
        shared_resources_exist = any(value > 2 for value in present_use_cost.values())

        # Increase the historical use cost for all used nodes by the amount used.
        for key, value in present_use_cost.items():
            historical_use_cost[key] += value

    # Finally, add the source and sinks to the routing tree to form
    # a completely routed net list.
    return {
        source: nodes | {source} | nets[source]
        for source, nodes in routes.items()
    }
