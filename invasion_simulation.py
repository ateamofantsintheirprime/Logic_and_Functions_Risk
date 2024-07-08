import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.widgets import Button
import random
 
# Define the graph as an adjacency list
graph = {
    32: [36,33,37],
	33: [23,35,37,34,36,22],
	34: [36,44,22,13],
	35: [37,33],
	36: [15, 13, 34, 29, 33, 32],
	37: [32, 35, 33],
	9:  [10, 12, 11, 15],
	10: [9, 12, 4],
	11: [15, 13, 14, 12],
	12: [10, 9, 11, 14],
	13: [15, 11, 14, 22, 34, 36],
	14: [12, 11, 13, 22],
	15: [9, 11, 13, 36],
	22: [14, 13, 34, 33],
	4: [10],
	29: [36]
}

troop_strength = {
    32: 0,
	33: 0,
	34: 0,
	35: 0,
	36: 0,
	37: 0,
	9:  0,
	10: 0,
	11: 0,
	12: 0,
	13: 0,
	14: 0,
	15: 0,
	22: 0,
	4: 0,
	29: 0
}

# Create a NetworkX graph from the adjacency list
G = nx.Graph(graph)
 
# Function to check if a path is Hamiltonian
def is_hamiltonian_path(G, path):
    return len(path) == len(G.nodes) and len(set(path)) == len(G.nodes)
 
def backtrack(current_paths, solutions):
    mega_path = []
    for p in current_paths:
        mega_path += p
    if len(mega_path) == len(G.nodes):
        if is_hamiltonian_path(G, set(mega_path)):
            solutions.append([p.copy() for p in current_paths])
        return
        #print("not hamiltonian")
    for p in current_paths:
        for neighbor in set(G.neighbors(p[-1])) - set(mega_path):
            
            p.append(neighbor)
            #print("adding", neighbor, "to path")
            backtrack(current_paths, solutions)
            p.pop(-1)

solutions = []

starting_points = [[2],[3]]
# ending_points = set([4,0])

backtrack(starting_points, solutions)

print("solutions", solutions)
random.shuffle(solutions)
sol = []
found = False
for s in solutions:
    found = True
    for sub_path in s:
        if troop_strength[sub_path[0]] <= sum([troop_strength[p_] for p_ in sub_path[1:]]):
            found = False
            break
    if found:
        print("valid found", s)
        sol = [s_.copy() for s_ in s]
        break
    
for sub_path in sol:
    print("starting power:", sub_path[0], troop_strength[sub_path[0]])
    print("path power:", sub_path[1:], sum([troop_strength[p_] for p_ in sub_path[1:]]))

new_edges = []
for sub_path in sol:
    print("sub path:", sub_path)
    new_edges += [(sub_path[i], sub_path[i + 1]) for i in range(len(sub_path) - 1)]
print(new_edges)

# Plotting setup
fig, ax = plt.subplots(figsize=(8, 8))
pos = nx.spring_layout(G)  # positions for all nodes
 
# Draw initial graph
nx.draw(G, pos, with_labels=True, node_color='skyblue', node_size=700, edge_color='gray', font_weight='bold', font_size=15, ax=ax)
plt.title(str(sol), fontsize=20)
nx.draw_networkx_edges(G, pos, edgelist=new_edges, edge_color='red', width=2, ax=ax)

plt.show()