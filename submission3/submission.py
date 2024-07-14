from collections import defaultdict, deque
import random
from typing import Optional, Tuple, Union, cast
from risk_helper.game import Game
from risk_shared.models.card_model import CardModel
from risk_shared.queries.query_attack import QueryAttack
from risk_shared.queries.query_claim_territory import QueryClaimTerritory
from risk_shared.queries.query_defend import QueryDefend
from risk_shared.queries.query_distribute_troops import QueryDistributeTroops
from risk_shared.queries.query_fortify import QueryFortify
from risk_shared.queries.query_place_initial_troop import QueryPlaceInitialTroop
from risk_shared.queries.query_redeem_cards import QueryRedeemCards
from risk_shared.queries.query_troops_after_attack import QueryTroopsAfterAttack
from risk_shared.queries.query_type import QueryType
from risk_shared.records.moves.move_attack import MoveAttack
from risk_shared.records.moves.move_attack_pass import MoveAttackPass
from risk_shared.records.moves.move_claim_territory import MoveClaimTerritory
from risk_shared.records.moves.move_defend import MoveDefend
from risk_shared.records.moves.move_distribute_troops import MoveDistributeTroops
from risk_shared.records.moves.move_fortify import MoveFortify
from risk_shared.records.moves.move_fortify_pass import MoveFortifyPass
from risk_shared.records.moves.move_place_initial_troop import MovePlaceInitialTroop
from risk_shared.records.moves.move_redeem_cards import MoveRedeemCards
from risk_shared.records.moves.move_troops_after_attack import MoveTroopsAfterAttack
from risk_shared.records.record_attack import RecordAttack
from risk_shared.records.types.move_type import MoveType


# We will store our enemy in the bot state.
class BotState():
	def __init__(self, game:Game):
		self.enemy: Optional[int] = None
		continents = game.state.map.get_continents()
		NA = set(continents[0])
		EU = set(continents[1])
		AS = set(continents[2])
		SA = set(continents[3])
		AF = set(continents[4])
		OC = set(continents[5])
		MEXICO = set([2])
		KAMCHATKA = set([21])
		MIDDLE_EAST = set([22])
		ICELAND = set([10])

		self.region_capture_priority = [ # In order of priority
			SA,
			SA | MEXICO, # maybe add west africa in future if safe
			# NA,
			NA | KAMCHATKA | ICELAND, # this attack neccesarily ends with our armies on choke points which is nice
			EU | AF | MIDDLE_EAST,
			AS,
			OC
		]

		self.war_focus = set()
		self.defense_focus = set()

def main():
	
	# Get the game object, which will connect you to the engine and
	# track the state of the game.
	game = Game()
	bot_state = BotState(game)
   
	# Respond to the engine's queries with your moves.
	while True:

		# Get the engine's query (this will block until you receive a query).
		query = game.get_next_query()
		# my_territories = game.state.get_territories_owned_by(game.state.me.player_id)

		# for continent in bot_state.attacking_continents:
		# if bot_state.attacking_continent in my_territories:
		#     bot_state.defending_continents.append(bot_state.attacking_continent)
		#     bot_state.attacking_continent = None # i think this works?
		# bot_state.war_focus = bot_state.region_capture_priority[0]
		for (region, next_region) in zip(bot_state.region_capture_priority[:-1], bot_state.region_capture_priority[1:]):
			bot_state.defense_focus.update(region)
			if controlling_region(game, region):
				bot_state.war_focus = next_region
			else:
				bot_state.war_focus = region
				break
		# if check_if_controlling_sa(game):
		#     if check_if_controlling_na(game):
		#         if check_if_controlling_eurafrica(game):
		#             bot_state.war_focus = set(game.state.map.get_continents()[5]) | set(game.state.map.get_continents()[2])
		#         else:
		#             bot_state.war_focus = set(game.state.map.get_continents()[1]) | set(game.state.map.get_continents()[4]) | set([22])
		#     else:
		#         bot_state.war_focus = set(game.state.map.get_continents()[0]) # NA
		# else:
		#     bot_state.war_focus = set(game.state.map.get_continents()[3]) # SA

		# Based on the type of query, respond with the correct move.
		def choose_move(query: QueryType) -> MoveType:
			match query:
				case QueryClaimTerritory() as q:
					return handle_claim_territory(game, bot_state, q)

				case QueryPlaceInitialTroop() as q:
					return handle_place_initial_troop(game, bot_state, q)

				case QueryRedeemCards() as q:
					return handle_redeem_cards(game, bot_state, q)

				case QueryDistributeTroops() as q:
					return handle_distribute_troops(game, bot_state, q)

				case QueryAttack() as q:
					return handle_attack(game, bot_state, q)

				case QueryTroopsAfterAttack() as q:
					return handle_troops_after_attack(game, bot_state, q)

				case QueryDefend() as q:
					return handle_defend(game, bot_state, q)

				case QueryFortify() as q:
					return handle_fortify(game, bot_state, q)
		
		# Send the move to the engine.
		game.send_move(choose_move(query))
				
def handle_claim_territory(game: Game, bot_state: BotState, query: QueryClaimTerritory) -> MoveClaimTerritory:
	unclaimed_territories = set(game.state.get_territories_owned_by(None))
	my_territories = set(game.state.get_territories_owned_by(game.state.me.player_id))
	# claim territories semi-randomly prioritising regions in order
	# print()
	# print("my_territories:", my_territories)
	# print("unclaimed_territories:", unclaimed_territories)
	for region in bot_state.region_capture_priority:
		unclaimed_in_region = region & unclaimed_territories
		# print("region:", region)
		# print("unclaimed in region:", unclaimed_in_region)
		if len(unclaimed_in_region) > 0:
			return game.move_claim_territory(query, unclaimed_in_region.pop())

def handle_place_initial_troop(game: Game, bot_state: BotState, query: QueryPlaceInitialTroop) -> MovePlaceInitialTroop:
	"""After all the territories have been claimed, you can place a single troop on one
	of your territories each turn until each player runs out of troops."""
	
	my_territories = set(game.state.get_territories_owned_by(game.state.me.player_id))

	# First try and place units INSIDE of our war focus, if we cant do that then try place them next to it.
	within_war_focus = bot_state.war_focus & my_territories
	adjacent_to_war_focus = adjacent_to_region(game, bot_state.war_focus) & my_territories
	print("war focus:",bot_state.war_focus)
	print("my_territories:",my_territories)
	print("within_war_focus:",within_war_focus)
	print("adjacent_to_war_focus:", adjacent_to_war_focus)
	print("adjacent_to_war_focus ALL:",adjacent_to_region(game, bot_state.war_focus))

	for territory in bot_state.war_focus:
		print("territory: ", territory)
		print("adjacent: ", set(game.state.map.get_adjacent_to(territory)) - set(bot_state.war_focus))

	if len(within_war_focus) > 0:
		in_danger_territory = max(within_war_focus, key=lambda x: threat(game,x))

	elif len(adjacent_to_war_focus) > 0:
		in_danger_territory = max(adjacent_to_war_focus, key=lambda x: threat(game,x))

	else:
		# I dont think this should be possible
		raise Exception

	return game.move_place_initial_troop(query, in_danger_territory)

def handle_redeem_cards(game: Game, bot_state: BotState, query: QueryRedeemCards) -> MoveRedeemCards:
	"""After the claiming and placing initial troops phases are over, you can redeem any
	cards you have at the start of each turn, or after killing another player."""

	# We will always redeem the minimum number of card sets we can until the 12th card set has been redeemed.
	# This is just an arbitrary choice to try and save our cards for the late game.

	# We always have to redeem enough cards to reduce our card count below five.
	card_sets: list[Tuple[CardModel, CardModel, CardModel]] = []
	cards_remaining = game.state.me.cards.copy()

	while len(cards_remaining) >= 5:
		card_set = game.state.get_card_set(cards_remaining)
		# According to the pigeonhole principle, we should always be able to make a set
		# of cards if we have at least 5 cards.
		assert card_set != None
		card_sets.append(card_set)
		cards_remaining = [card for card in cards_remaining if card not in card_set]

	# Remember we can't redeem any more than the required number of card sets if 
	# we have just eliminated a player.
	if game.state.card_sets_redeemed > 12 and query.cause == "turn_started":
		card_set = game.state.get_card_set(cards_remaining)
		while card_set != None:
			card_sets.append(card_set)
			cards_remaining = [card for card in cards_remaining if card not in card_set]
			card_set = game.state.get_card_set(cards_remaining)

	return game.move_redeem_cards(query, [(x[0].card_id, x[1].card_id, x[2].card_id) for x in card_sets])


def handle_distribute_troops(game: Game, bot_state: BotState, query: QueryDistributeTroops) -> MoveDistributeTroops:
	"""After you redeem cards (you may have chosen to not redeem any), you need to distribute
	all the troops you have available across your territories. This can happen at the start of
	your turn or after killing another player.
	"""
	print("starting to distribute troops")
	# We will distribute troops across our border territories.
	total_troops = game.state.me.troops_remaining
	distributions = defaultdict(lambda: 0)


	# We need to remember we have to place our matching territory bonus
	# if we have one.
	print("adding matching territory bonus")
	if len(game.state.me.must_place_territory_bonus) != 0:
		assert total_troops >= 2
		distributions[game.state.me.must_place_territory_bonus[0]] += 2
		total_troops -= 2


	# Our first priority is to stack along the border territories of continents we are trying to defend.
	# This will be a choke point if we are in control of the territory, and will be all over the territory
	# if we are not in control (Not ideal)
	border_territories = set(game.state.get_all_border_territories(
		game.state.get_territories_owned_by(game.state.me.player_id)
	))

	defensive_borders = border_territories & bot_state.defense_focus


	print("reinforcing defensive territories")
	defensive_priorities = sorted(list(defensive_borders), key= lambda x: threat(game,x), reverse=True)
	for territory in defensive_priorities:
		t = threat(game,territory)
		if total_troops == 0:
			break 
		if round(t) > 0:
			distributions[territory] += min(total_troops, round(t))
			total_troops -= min(total_troops, round(t))
	

	if total_troops > 0:
		# If we still have remaining troops, we add forces to our front line in the continent we are currently attacking
		print("reinforcing front line")
		war_focus_armies = set()
		# our 'war focus armies' represent our armies within the continent that we are invading
		# the continent / group of territories we are invading is our "war focus" 

		for territory in bot_state.war_focus:
			for neighbour in game.state.map.get_adjacent_to(territory):
				if game.state.territories[neighbour].occupier == game.state.me.player_id:
					war_focus_armies.add(neighbour)

		if len(war_focus_armies) > 0:
			print("potential deathstacks:", war_focus_armies)
			current_deathstack = max(war_focus_armies, key= lambda x: game.state.territories[x].troops + distributions[x] + 0.001 * threat(game, x))
			distributions[current_deathstack] += total_troops
			total_troops = 0
			# Stick all remain  ing troops on the current largest deathstack in the war_focus
	if total_troops > 0 and len(defensive_priorities):

		current_deathstack = max(defensive_priorities, key= lambda x: game.state.territories[x].troops + distributions[x] + 0.001 * threat(game, x))
		distributions[current_deathstack] += total_troops
		total_troops = 0
	if total_troops > 0:
		troops_per_territory = total_troops // len(border_territories)
		leftover_troops = total_troops % len(border_territories)
		for territory in border_territories:
			distributions[territory] += troops_per_territory
	
		# The leftover troops will be put some territory (we don't care)
		distributions[border_territories.pop()] += leftover_troops

	print(distributions.items())

	return game.move_distribute_troops(query, distributions)

	# if len(game.state.recording) < 4000:
		
	
	# else:
	#     my_territories = game.state.get_territories_owned_by(game.state.me.player_id)
	#     weakest_players = sorted(game.state.players.values(), key=lambda x: sum(
	#         [game.state.territories[y].troops for y in game.state.get_territories_owned_by(x.player_id)]
	#     ))

	#     for player in weakest_players:
	#         bordering_enemy_territories = set(game.state.get_all_adjacent_territories(my_territories)) & set(game.state.get_territories_owned_by(player.player_id))
	#         if len(bordering_enemy_territories) > 0:
	#             print("my territories", [game.state.map.get_vertex_name(x) for x in my_territories])
	#             print("bordering enemies", [game.state.map.get_vertex_name(x) for x in bordering_enemy_territories])
	#             print("adjacent to target", [game.state.map.get_vertex_name(x) for x in game.state.map.get_adjacent_to(list(bordering_enemy_territories)[0])])
	#             selected_territory = list(set(game.state.map.get_adjacent_to(list(bordering_enemy_territories)[0])) & set(my_territories))[0]
	#             distributions[selected_territory] += total_troops
	#             break


	# return game.move_distribute_troops(query, distributions)


def handle_attack(game: Game, bot_state: BotState, query: QueryAttack) -> Union[MoveAttack, MoveAttackPass]:
	print("STARTING TURN ", len(game.state.recording))
	# bot_state.war_focus = set()
	my_territories = set(game.state.get_territories_owned_by(game.state.me.player_id))
	bot_state.max_search_depth = 1000

	def covers_war_focus(mega_path:set):
		return bot_state.war_focus.issubset(mega_path | my_territories)

	def hamiltonian_warpath(current_paths:list[list[int]], solutions:list):
		# Check if we have enough power so far and dont progress if we dont have enough power
		# In future this should account for gaining cards thanks to eliminating players
		bot_state.max_search_depth -= 1
		if bot_state.max_search_depth <= 0:
			print("exceeding max search depth")
			return
		for sub_path in current_paths:
			if game.state.territories[sub_path[0]].troops <= sum([game.state.territories[t].troops for t in sub_path[1:]]):
				return
		# print("current_paths:", current_paths)
		all_nodes_in_paths = set()
		for sub_path in current_paths:
			all_nodes_in_paths.update(sub_path)
		all_possible_neighbours = set()
		for sub_path in current_paths:
			all_possible_neighbours.update(set(game.state.map.get_adjacent_to(sub_path[-1])) & (bot_state.war_focus - set(all_nodes_in_paths) - my_territories))
		if len(all_possible_neighbours) == 0:
			if covers_war_focus(all_nodes_in_paths):
				solutions.append([p.copy() for p in current_paths])
			return
		for sub_path in current_paths:
			for neighbour in set(game.state.map.get_adjacent_to(sub_path[-1])) & (bot_state.war_focus - set(all_nodes_in_paths) - my_territories):
				sub_path.append(neighbour)
				hamiltonian_warpath(current_paths, solutions)
				sub_path.pop(-1)
	

	# war_focus
	print("war focus: ", bot_state.war_focus)
	path_solutions = []
	path_starting_points = get_starting_territories(game, bot_state)

	preferred_ending_points = []

	print("my_territories: ", my_territories, flush=True)
	print("starting points: ", path_starting_points, flush=True)
	starting_point_power = sum([game.state.territories[t[0]].troops for t in path_starting_points])
	print("starting point power:", starting_point_power, flush=True)
	enemy_territories_in_war_focus = bot_state.war_focus - my_territories
	print("enemy territories in war focus:", enemy_territories_in_war_focus, flush=True)
	war_focus_enemy_power = sum([game.state.territories[t].troops for t in enemy_territories_in_war_focus])
	print("war_focus_enemy_power:", war_focus_enemy_power, flush=True)

	if starting_point_power > war_focus_enemy_power: # Dont factor in troops left behind, ends up making this too unoptimistic because attacking with high numbers is very good
		hamiltonian_warpath(path_starting_points, path_solutions)
	else:
		print("heuristic based check failed", flush=True)
		return game.move_attack_pass(query)
	sol = []
	# print("path solutions:", path_solutions,flush=True)
	print(f"found {len(path_solutions)}, potential solutions")
	for s in path_solutions:
		found = True
		# print("one possible solution: ", s)
		for sub_path in s:
			# print("starting power:", sub_path[0],game.state.territories[sub_path[0]].troops)
			# print("path power:", sub_path[1:], len(sub_path[1:]), sum([game.state.territories[p_].troops for p_ in sub_path[1:]]))
			# print("path validity:", game.state.territories[sub_path[0]].troops > sum([game.state.territories[t].troops for t in sub_path[1:]]))

			if game.state.territories[sub_path[0]].troops <= sum([game.state.territories[t].troops for t in sub_path[1:]]):
				found = False
				break
		if found:
			# print("valid path found:", s,flush=True)
			sol = [s_.copy() for s_ in s]

	sol = [s for s in sol if len(s) > 1]

	print("sol:", sol, flush=True)
	if sol == []:
		print("no valid paths",flush=True)
		return game.move_attack_pass(query)
	# else:
	#     for sub_path in sol: 

	path_to_progress_this_turn = random.choice(sol)
	source = path_to_progress_this_turn[0]
	target = path_to_progress_this_turn[1]
	print(f"attacking from {source} to {target} with {min(3, game.state.territories[source].troops - 1)} troops", flush=True)
	print(game.state.territories[source].troops - 1)
	return game.move_attack(query, source, target, min(3, game.state.territories[source].troops - 1))


def handle_troops_after_attack(game: Game, bot_state: BotState, query: QueryTroopsAfterAttack) -> MoveTroopsAfterAttack:
	"""After conquering a territory in an attack, you must move troops to the new territory."""
	
	# First we need to get the record that describes the attack, and then the move that specifies
	# which territory was the attacking territory.
	record_attack = cast(RecordAttack, game.state.recording[query.record_attack_id])
	move_attack = cast(MoveAttack, game.state.recording[record_attack.move_attack_id])

	# We will always move the maximum number of troops we can.
	print(f"moving {game.state.territories[move_attack.attacking_territory].troops - 1}", flush=True)
	return game.move_troops_after_attack(query, game.state.territories[move_attack.attacking_territory].troops - 1)


def handle_defend(game: Game, bot_state: BotState, query: QueryDefend) -> MoveDefend:
	"""If you are being attacked by another player, you must choose how many troops to defend with."""

	# We will always defend with the most troops that we can.

	# First we need to get the record that describes the attack we are defending against.
	move_attack = cast(MoveAttack, game.state.recording[query.move_attack_id])
	defending_territory = move_attack.defending_territory
	
	# We can only defend with up to 2 troops, and no more than we have stationed on the defending
	# territory.
	defending_troops = min(game.state.territories[defending_territory].troops, 2)
	return game.move_defend(query, defending_troops)


def handle_fortify(game: Game, bot_state: BotState, query: QueryFortify) -> Union[MoveFortify, MoveFortifyPass]:
	"""At the end of your turn, after you have finished attacking, you may move a number of troops between
	any two of your territories (they must be adjacent)."""

	# We will always fortify towards the most powerful player (player with most troops on the map) to defend against them.
	my_territories = game.state.get_territories_owned_by(game.state.me.player_id)
	total_troops_per_player = {}
	for player in game.state.players.values():
		total_troops_per_player[player.player_id] = sum([game.state.territories[x].troops for x in game.state.get_territories_owned_by(player.player_id)])

	most_powerful_player = max(total_troops_per_player.items(), key=lambda x: x[1])[0]

	# If we are the most powerful, we will pass.
	if most_powerful_player == game.state.me.player_id:
		return game.move_fortify_pass(query)
	
	# Otherwise we will find the shortest path between our territory with the most troops
	# and any of the most powerful player's territories and fortify along that path.
	candidate_territories = game.state.get_all_border_territories(my_territories)
	most_troops_territory = max(candidate_territories, key=lambda x: game.state.territories[x].troops)

	# To find the shortest path, we will use a custom function.
	shortest_path = find_shortest_path_from_vertex_to_set(game, most_troops_territory, set(game.state.get_territories_owned_by(most_powerful_player)))
	# We will move our troops along this path (we can only move one step, and we have to leave one troop behind).
	# We have to check that we can move any troops though, if we can't then we will pass our turn.
	if len(shortest_path) > 0 and game.state.territories[most_troops_territory].troops > 1:
		return game.move_fortify(query, shortest_path[0], shortest_path[1], game.state.territories[most_troops_territory].troops - 1)
	else:
		return game.move_fortify_pass(query)

# def check_if_controlling_sa(game:Game):
#     my_territories = set(game.state.get_territories_owned_by(game.state.me.player_id))
#     # sa = set([30,31,29,28])
#     sa = set(game.state.map.get_continents()[3])
#     return set(sa).issubset(my_territories)

# def check_if_controlling_na(game:Game):
#     my_territories = set(game.state.get_territories_owned_by(game.state.me.player_id))
#     na = set(game.state.map.get_continents()[0])
#     # na = set([0,1,2,3,4,5,6,7,8])
#     return set(na).issubset(my_territories)

# def check_if_controlling_eurafrica(game:Game):
#     my_territories = set(game.state.get_territories_owned_by(game.state.me.player_id))
#     eurafrica = set(game.state.map.get_continents()[1]) | set(game.state.map.get_continents()[4]) | set([22])
#     return set(eurafrica).issubset(my_territories)

def controlling_region(game:Game, region:set[int]):
	my_territories = set(game.state.get_territories_owned_by(game.state.me.player_id))
	return region.issubset(my_territories)

def get_starting_territories(game:Game, bot_state:BotState):
	result = set()
	for territory in bot_state.war_focus:
		for neighbour in game.state.map.get_adjacent_to(territory):
			if game.state.territories[neighbour].occupier == game.state.me.player_id:
				if game.state.territories[neighbour].troops >= 3:
					result.add(neighbour)
	return [[t] for t in result]

def threat(game:Game, victim:int):
	threat = 0
	for neighbour_id in game.state.map.get_adjacent_to(victim):
		if game.state.territories[neighbour_id].occupier != game.state.me.player_id:
			threat += min(0,game.state.territories[neighbour_id].troops - 1)
	return threat * 1.25 + 2 - game.state.territories[victim].troops
	# This is oversimplified and does not account for cards


def take_continent(game:Game, source:int, continent:str):
	# first do a simple check if we have enough forces.
	assert game.state.territories[source].occupier == game.state.me.player_id

	territories_of_continent = set(game.state.map.get_continents()[continent])
	my_territories = set(game.state.get_territories_owned_by(game.state.me.player_id))
	enemy_territories = territories_of_continent - my_territories

	if len(enemy_territories) == 0:
		print("you already have the continent!")
		return []
	
	total_enemy_power = sum([game.state.territories[t].troops for t in enemy_territories])

	if game.state.territories[source].troops - len(territories_of_continent) < total_enemy_power * 1.25 + 2:
		print("not strong enough!")
		return []



def find_shortest_path_from_vertex_to_set(game: Game, source: int, target_set: set[int]) -> list[int]:
	"""Used in move_fortify()."""

	# We perform a BFS search from our source vertex, stopping at the first member of the target_set we find.
	queue = deque()
	queue.appendleft(source)

	current = queue.pop()
	parent = {}
	seen = {current: True}

	while len(queue) != 0:
		if current in target_set:
			break

		for neighbour in game.state.map.get_adjacent_to(current):
			if neighbour not in seen:
				seen[neighbour] = True
				parent[neighbour] = current
				queue.appendleft(neighbour)

		current = queue.pop()

	path = []
	while current in parent:
		path.append(current)
		current = parent[current]

	return path[::-1]


def kill_deathstack(game:Game):
# Check if i have the largest deathstack in the game
	my_territories = set(game.state.get_territories_owned_by(game.state.me.player_id))
	enemy_territories = set(game.state.territories.keys()) - my_territories

	strongest_territory = max(my_territories, key=lambda x: game.state.territories[x].troops)
	scariest_territory = max(enemy_territories, key=lambda x: game.state.territories[x].troops)

	if game.state.territories[strongest_territory].troops > game.state.territories[scariest_territory].troops * 1.15:
		print("i can kill the largest deathstack")
		path = find_shortest_path_from_vertex_to_set(game, strongest_territory, scariest_territory)
		print(f"path to them: {path}")


def evaluate_troop_movement_quality(game:Game, territory_mask:set[int], troop_source:int, troop_dest:int, troop_number:int):
	my_territories = set(game.state.get_territories_owned_by(game.state.me.player_id))
	border_territories = set(game.state.get_all_adjacent_territories(my_territories))

	non_border_territories = my_territories - border_territories

	quality= 0

	for terr in non_border_territories:
		quality -= game.state.territories[terr].troops - 1
		# Punish for having troops in useless spots
	
	for terr in border_territories:
		quality -= min(0, threat(game, terr))
		# Punish for having poorly fortified borders


# def take_continent(game:Game, cont_territories:set[int]):
#     # find path through continent
#     my_territories = set(game.state.get_territories_owned_by(game.state.me.player_id)) & cont_territories
#     enemy_territories = cont_territories ^ my_territories
#     visited = set(my_territories)

def adjacent_to_region(game:Game, region:set[int]):
	result = set()
	for territory in region:
		result.update(set([t for t in game.state.map.get_adjacent_to(territory)]) - region)
	return result


if __name__ == "__main__":
	main()