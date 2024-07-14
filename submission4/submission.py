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
		WEST_AFRICA = set([36])
		KAMCHATKA = set([21])
		MIDDLE_EAST = set([22])
		ICELAND = set([10])

		self.region_capture_priority = [ # In order of priority
			SA,
			SA | MEXICO | WEST_AFRICA,
			# AF,
			NA,
			NA | KAMCHATKA | ICELAND, # this attack neccesarily ends with our armies on choke points which is nice
			EU | AF | MIDDLE_EAST,
			AS,
			OC
		]

		self.war_focus = set()
		self.defense_focus = set()
		self.chosen_attack_path = []
		self.max_search_depth = 10000

def main():
	
	# Get the game object, which will connect you to the engine and
	# track the state of the game.
	game = Game()
	bot_state = BotState(game)
   
	# Respond to the engine's queries with your moves.
	while True:

		# Get the engine's query (this will block until you receive a query).
		query = game.get_next_query()
		get_focuses(bot_state, game)
		def choose_move(query: QueryType) -> MoveType:
			match query:
				case QueryClaimTerritory() as q:
					return handle_claim_territory(game, bot_state, q)

				case QueryPlaceInitialTroop() as q:
					return handle_place_initial_troop(game, bot_state, q)

				case QueryRedeemCards() as q:
					return handle_redeem_cards(game, bot_state, q)

				case QueryDistributeTroops() as q:
					res = handle_distribute_troops(game, bot_state, q)
					calculate_attack_path(game, bot_state)
					return res

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
	# print( flush=True)
	# print("my_territories:", my_territories test
	# print("unclaimed_territories:", unclaimed_territories, flush=True)
	for region in bot_state.region_capture_priority:
		unclaimed_in_region = region & unclaimed_territories
		# print("region:", region, flush=True)
		# print("unclaimed in region:", unclaimed_in_region, flush=True)
		if len(unclaimed_in_region) > 0:
			return game.move_claim_territory(query, unclaimed_in_region.pop())
	raise Exception

def handle_place_initial_troop(game: Game, bot_state: BotState, query: QueryPlaceInitialTroop) -> MovePlaceInitialTroop:
	my_territories = set(game.state.get_territories_owned_by(game.state.me.player_id))
	bot_state.max_search_depth = 2000

	def covers_war_focus(mega_path:set):
		return bot_state.war_focus.issubset(mega_path | my_territories)

	def hamiltonian_warpath(current_paths:list[list[int]], solutions:list):
		# In future this should account for gaining cards thanks to eliminating players
		bot_state.max_search_depth -= 1
		if bot_state.max_search_depth <= 0:
			print("exceeding max search depth", flush=True)
			return
		# print("current_paths:", current_paths, flush=True)
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
	
	def combinations(values: list[int], length:int):
		if length == 1:
			return [[v] for v in values]
		if length == 0:
			return []
		result = []
		for i in range(len(values)-1):
			for c in combinations(values[i+1:], length-1):
				result.append([values[i]] + c)
		return result

	starting_point_combinations = []
	
	ideal_ending_points = set(game.state.get_all_border_territories(
		list(bot_state.war_focus)
	)) - my_territories

	
	border_territories = set(game.state.get_all_border_territories(
		game.state.get_territories_owned_by(game.state.me.player_id)
	))

	within_war_focus = bot_state.war_focus & border_territories
	adjacent_to_war_focus = adjacent_to_region(game, bot_state.war_focus) & border_territories

	# All combinations of my territories that are adjacent to enemy territories

	sol = None
	num_starting_points = 1
	while sol == None:
		starting_point_combinations = combinations(list(bot_state.war_focus & border_territories), num_starting_points)
		for starting_points in starting_point_combinations:
			path_solutions = []
			hamiltonian_warpath([[p] for p in starting_points], path_solutions)
			if len(path_solutions) > 0:
				print("path solutions:", path_solutions, flush=True)
				# get the solution which has the most of its sub_paths ending at desired ending points
				most_ideal_solution = max(path_solutions, key=lambda x: len([s_ for s_ in x if s_[-1] in ideal_ending_points]))
				print("most ideal solution: ", most_ideal_solution, flush=True)
				sol = [s_.copy() for s_ in most_ideal_solution]
				break
		# if there is no solution found with this number of starting points, we increase the number of possible starting points and check again. hopefully this isnt too slow.
		num_starting_points += 1

	print("found sol: ", sol, flush=True)
	chosen_starting_points = [s[0] for s in sol]
	most_threatened = max(chosen_starting_points, key=lambda x: threat(game,x))

	return game.move_place_initial_troop(query, most_threatened)

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
	distributions = defaultdict(lambda: 0)
	total_troops = game.state.me.troops_remaining
	get_focuses(bot_state, game)

	if len(game.state.me.must_place_territory_bonus) != 0:
		assert total_troops >= 2
		distributions[game.state.me.must_place_territory_bonus[0]] += 2
		total_troops -= 2

	my_territories = set(game.state.get_territories_owned_by(game.state.me.player_id))
	border_territories = set(game.state.get_all_border_territories(my_territories))
	defensive_borders = border_territories & bot_state.defense_focus

	print("reinforcing defensive territories", flush=True)
	defensive_priorities = sorted(list(defensive_borders), key= lambda x: threat(game,x), reverse=True)
	for territory in defensive_priorities:
		t = threat(game,territory)
		print(f"threat to {territory}: {t}", flush=True)
		if total_troops == 0:
			break
		if round(t) > 0:
			print(f"reinforcing defensive territory: {territory}", flush=True)
			distributions[territory] += min(total_troops, round(t))
			total_troops -= min(total_troops, round(t))
	
	if total_troops == 0:
		return game.move_distribute_troops(query, distributions)


	def covers_war_focus(mega_path:set):
		return bot_state.war_focus.issubset(mega_path | my_territories)

	def hamiltonian_warpath(current_paths:list[list[int]], solutions:list):
		# In future this should account for gaining cards thanks to eliminating players
		bot_state.max_search_depth -= 1
		if bot_state.max_search_depth <= 0:
			print("exceeding max search depth", flush=True)
			return
		# print("current_paths:", current_paths, flush=True)
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
	
	def combinations(values: list[int], length:int):
		if length == 1:
			return [[v] for v in values]
		if length == 0:
			return []
		result = []
		for i in range(len(values)-1):
			for c in combinations(values[i+1:], length-1):
				result.append([values[i]] + c)
		return result

	starting_point_combinations = []

	ideal_ending_points = set(game.state.get_all_border_territories(
		bot_state.war_focus
	)) - my_territories

	
	border_territories = set(game.state.get_all_border_territories(
		game.state.get_territories_owned_by(game.state.me.player_id)
	))
	# All combinations of my territories that are adjacent to enemy territories

	print("looking for front line to reinforce", flush=True)

	if len(bot_state.war_focus & border_territories) == 1:
		target =(bot_state.war_focus & border_territories).pop()
		distributions[target] += total_troops
		print(f"distributing to only front line: {target}")
		return game.move_distribute_troops(query, distributions)

	print("multiple start points, investigating different options")

	sol = []
	num_starting_points = 1
	print("potential starting points: ",bot_state.war_focus & border_territories )
	while len(sol) == 0:
		print(f"calculating combinations of len {num_starting_points}")
		starting_point_combinations = combinations(list(bot_state.war_focus & border_territories), num_starting_points)
		most_optimal_solution = None
		for starting_points in starting_point_combinations:
			print(f"investigating starting points: {starting_points}", flush=True)
			path_solutions = []
			bot_state.max_search_depth = 20000 // len(starting_point_combinations)
			hamiltonian_warpath([[p] for p in starting_points], path_solutions)
			if len(path_solutions) > 0:
				most_ends_at_preferred_points = max([len([s_ for s_ in x if s_[-1] in ideal_ending_points]) for x in path_solutions])
				end_point_filtered = [p for p in path_solutions if len([s_ for s_ in p if s_[-1] in ideal_ending_points]) == most_ends_at_preferred_points]


				if most_optimal_solution != None:
					end_point_filtered.append(most_optimal_solution)
				most_optimal_solution = max(end_point_filtered, key=lambda x:min(estimated_remaining_troops(game, s) for s in x))

				print("path solutions:", path_solutions, flush=True)
				# # get the solution which has the most of its sub_paths ending at desired ending points
				# most_ideal_solution = max(path_solutions, key=lambda x: len([s_ for s_ in x if s_[-1] in ideal_ending_points]))
				print("most optimal solution: ", most_optimal_solution, flush=True)
				print("min remaining: ", min(estimated_remaining_troops(game, s) for s in most_optimal_solution), flush=True)
				sol = [s_.copy() for s_ in most_optimal_solution]
		# if there is no solution found with this number of starting points, we increase the number of possible starting points and check again. hopefully this isnt too slow.
		if most_optimal_solution != None:
			break
		if num_starting_points >= len(bot_state.war_focus & border_territories):
			break
		num_starting_points += 1

	print("found sol: ", sol, flush=True)
	for path in sol:
		needed = round(-estimated_remaining_troops(game, path)*1.25)
		for p in path:
			print(f"point: {p}, power: {game.state.territories[p].troops}")
		print("needed:", needed)
		print("total_troops:", total_troops)
		if needed >= 1:
			distributions[path[0]] += min(needed, total_troops)
			print(f"adding {min(needed, total_troops)} to {path[0]}")
			total_troops -= min(needed, total_troops)

	if total_troops > 0:
		troops_per_territory = total_troops // len(border_territories)
		leftover_troops = total_troops % len(border_territories)
		for territory in border_territories:
			distributions[territory] += troops_per_territory
		distributions[border_territories.pop()] += leftover_troops

	print("distributions")
	print(distributions.items(), flush=True)


	return game.move_distribute_troops(query, distributions)

def handle_distribute_troops_old(game: Game, bot_state: BotState, query: QueryDistributeTroops) -> MoveDistributeTroops:
	"""After you redeem cards (you may have chosen to not redeem any), you need to distribute
	all the troops you have available across your territories. This can happen at the start of
	your turn or after killing another player.
	"""
	print("starting to distribute troops", flush=True)
	# We will distribute troops across our border territories.
	total_troops = game.state.me.troops_remaining
	distributions = defaultdict(lambda: 0)


	# We need to remember we have to place our matching territory bonus
	# if we have one.
	print("adding matching territory bonus", flush=True)
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


	print("reinforcing defensive territories", flush=True)
	defensive_priorities = sorted(list(defensive_borders), key= lambda x: threat(game,x), reverse=True)
	for territory in defensive_priorities:
		t = threat(game,territory)
		print(f"threat to {territory}: {t}")
		if total_troops == 0:
			break
		if round(t) > 0:
			print(f"reinforcing defensive territory: {territory}", flush=True)
			distributions[territory] += min(total_troops, round(t))
			total_troops -= min(total_troops, round(t))
	

	if total_troops > 0:
		# If we still have remaining troops, we add forces to our front line in the continent we are currently attacking
		print("reinforcing front line", flush=True)
		my_territories = set(game.state.get_territories_owned_by(game.state.me.player_id))

		war_focus_armies = set()
		# our 'war focus armies' represent our armies within the continent that we are invading
		# the continent / group of territories we are invading is our "war focus" 

		for territory in bot_state.war_focus - my_territories: # Reinforce my armies adjacent to enemy territories in war focus
			for neighbour in game.state.map.get_adjacent_to(territory):
				if game.state.territories[neighbour].occupier == game.state.me.player_id:
					war_focus_armies.add(neighbour)

		if len(war_focus_armies) > 0:
			print("potential deathstacks:", war_focus_armies, flush=True)
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

	print(distributions.items(), flush=True)

	return game.move_distribute_troops(query, distributions)

def handle_attack(game: Game, bot_state: BotState, query: QueryAttack) -> Union[MoveAttack, MoveAttackPass]:
	# calculate_attack_path(game, bot_state)
	print("turn: ", len(game.state.recording), flush=True)
	get_focuses(bot_state, game)

	if len(bot_state.chosen_attack_path) > 0:
		if min(estimated_remaining_troops(game, p) for p in bot_state.chosen_attack_path) <= 2:
			calculate_attack_path(game, bot_state)
	else:
		my_territories = set(game.state.get_territories_owned_by(game.state.me.player_id))
		border_territories = set(game.state.get_all_border_territories(my_territories))

		within_war_focus = bot_state.war_focus
		adjacent_to_war_focus = adjacent_to_region(game, bot_state.war_focus)
		enemy_power=sum([game.state.territories[t].troops for t in within_war_focus - my_territories])
		my_power = sum([game.state.territories[t].troops for t in (within_war_focus|border_territories)&my_territories])
		if my_power > 0.857*enemy_power + len(within_war_focus - my_territories)+ 1:
			calculate_attack_path(game,bot_state)


	print("sol:", bot_state.chosen_attack_path, flush=True)
	if bot_state.chosen_attack_path == []:
		print("no valid paths",flush=True)
		return game.move_attack_pass(query)

	path_to_progress_this_turn = bot_state.chosen_attack_path.pop(0)
	
	source = path_to_progress_this_turn[0]
	target = path_to_progress_this_turn[1]
	bot_state.chosen_attack_path.append(path_to_progress_this_turn)
	print(f"attacking from {source} to {target} with {min(3, game.state.territories[source].troops - 1)} troops", flush=True)
	print(game.state.territories[source].troops - 1, flush=True)
	return game.move_attack(query, source, target, min(3, game.state.territories[source].troops - 1))


def handle_troops_after_attack(game: Game, bot_state: BotState, query: QueryTroopsAfterAttack) -> MoveTroopsAfterAttack:
	"""After conquering a territory in an attack, you must move troops to the new territory."""
	
	# First we need to get the record that describes the attack, and then the move that specifies
	# which territory was the attacking territory.
	record_attack = cast(RecordAttack, game.state.recording[query.record_attack_id])
	move_attack = cast(MoveAttack, game.state.recording[record_attack.move_attack_id])
	found = False
	for sub_path in bot_state.chosen_attack_path:
		if move_attack.attacking_territory == sub_path[0]:
			sub_path.pop(0)
			found = True
			break
	if not found:
		raise Exception

	bot_state.chosen_attack_path = [p for p in bot_state.chosen_attack_path if len(p) > 1]

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
	my_territories = set(game.state.get_territories_owned_by(game.state.me.player_id))
	border_territories = set(game.state.get_all_border_territories(my_territories))
	internal_territories = my_territories - border_territories
	if len(internal_territories) == 0:
		return game.move_fortify_pass(query)


	most_troops_territory = max(internal_territories, key=lambda x: game.state.territories[x].troops)
	if game.state.territories[most_troops_territory].troops == 1:
		return game.move_fortify_pass(query)

	nearest_border = None
	path_to_border = [[most_troops_territory]]
	visited = [most_troops_territory]
	while True:
		path = path_to_border.pop(0)
		if path[-1] in border_territories:
			break
			
		for neighbour in game.state.map.get_adjacent_to(path[-1]):
			if neighbour not in visited:
				visited.append(neighbour)

				path_to_border.append(path + [neighbour])

	print(path)
	return game.move_fortify(query, path[0], path[1], game.state.territories[most_troops_territory].troops - 1)


def handle_fortify_old(game: Game, bot_state: BotState, query: QueryFortify) -> Union[MoveFortify, MoveFortifyPass]:
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
		total_troops_per_player = {}
		for player in game.state.players.values():
			if player.player_id != game.state.me.player_id:
				total_troops_per_player[player.player_id] = sum([game.state.territories[x].troops for x in game.state.get_territories_owned_by(player.player_id)])

		most_powerful_player = max(total_troops_per_player.items(), key=lambda x: x[1])[0]

		# print("NOT FORTIFYING")
		# return game.move_fortify_pass(query)
	
	# Otherwise we will find the shortest path between our territory with the most troops
	# and any of the most powerful player's territories and fortify along that path.
	candidate_territories = game.state.get_all_border_territories(my_territories)
	most_troops_territory = max(candidate_territories, key=lambda x: game.state.territories[x].troops)

	# To find the shortest path, we will use a custom function.
	shortest_path = find_shortest_path_from_vertex_to_set(game, most_troops_territory, set(game.state.get_territories_owned_by(most_powerful_player)))
	# We will move our troops along this path (we can only move one step, and we have to leave one troop behind).
	# We have to check that we can move any troops though, if we can't then we will pass our turn.
	if len(shortest_path) > 0 and game.state.territories[most_troops_territory].troops > 1:
		print("FORTIFYING")
		return game.move_fortify(query, shortest_path[0], shortest_path[1], game.state.territories[most_troops_territory].troops - 1)
	else:
		print("NOT FORTIFYING")
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
	print(f"victim: {victim}")
	print(f"victim power: {game.state.territories[victim].troops}")
	for neighbour_id in game.state.map.get_adjacent_to(victim):
		if game.state.territories[neighbour_id].occupier != game.state.me.player_id:
			print(f"neighbour: {neighbour_id}")
			print(f"neighbour_power: {min(0,game.state.territories[neighbour_id].troops)}")
			threat += min(0,game.state.territories[neighbour_id].troops)
	return threat * 1.25 + 2 - game.state.territories[victim].troops
	# This is oversimplified and does not account for cards


def take_continent(game:Game, source:int, continent:str):
	# first do a simple check if we have enough forces.
	assert game.state.territories[source].occupier == game.state.me.player_id

	territories_of_continent = set(game.state.map.get_continents()[continent])
	my_territories = set(game.state.get_territories_owned_by(game.state.me.player_id))
	enemy_territories = territories_of_continent - my_territories

	if len(enemy_territories) == 0:
		print("you already have the continent!", flush=True)
		return []
	
	total_enemy_power = sum([game.state.territories[t].troops for t in enemy_territories])

	if game.state.territories[source].troops - len(territories_of_continent) < total_enemy_power * 1.25 + 2:
		print("not strong enough!", flush=True)
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
		print("i can kill the largest deathstack", flush=True)
		path = find_shortest_path_from_vertex_to_set(game, strongest_territory, scariest_territory)
		print(f"path to them: {path}", flush=True)


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

def calculate_attack_path(game:Game, bot_state:BotState):
	# bot_state.war_focus = set()
	print("CALCULATING ATTACK ", flush=True)
	my_territories = set(game.state.get_territories_owned_by(game.state.me.player_id))
	bot_state.max_search_depth = 10000
	get_focuses(bot_state, game)

	def covers_war_focus(mega_path:set):
		return bot_state.war_focus.issubset(mega_path | my_territories)

	def hamiltonian_warpath(current_paths:list[list[int]], solutions:list):
		# In future this should account for gaining cards thanks to eliminating players
		bot_state.max_search_depth -= 1
		if bot_state.max_search_depth <= 0:
			print("exceeding max search depth", flush=True)
			return
		# Check if we have enough power so far and dont progress if we dont have enough power
		for sub_path in current_paths:
			if len(sub_path) > 1 and estimated_remaining_troops(game, sub_path) <= 1:
				return
		all_nodes_in_paths = set()
		for sub_path in current_paths:
			all_nodes_in_paths.update(sub_path)
		all_possible_neighbours = set()
		for sub_path in current_paths:
			all_possible_neighbours.update(set(game.state.map.get_adjacent_to(sub_path[-1])) & (bot_state.war_focus - set(all_nodes_in_paths) - my_territories))
		if len(all_possible_neighbours) == 0:
			if covers_war_focus(all_nodes_in_paths):
				solutions.append([p.copy() for p in current_paths if len(p) > 1])
			return
		# print("current paths: ", current_paths, flush=True)
		for sub_path in current_paths:
			# print("neighbours to end of sub_path:", set(game.state.map.get_adjacent_to(sub_path[-1])))
			# print("attackable territories:", (bot_state.war_focus - set(all_nodes_in_paths) - my_territories))
			for neighbour in set(game.state.map.get_adjacent_to(sub_path[-1])) & (bot_state.war_focus - set(all_nodes_in_paths) - my_territories):
				sub_path.append(neighbour)
				hamiltonian_warpath(current_paths, solutions)
				sub_path.pop(-1)
	

	# war_focus
	print("war focus: ", bot_state.war_focus, flush=True)
	path_solutions = []
	path_starting_points = get_starting_territories(game, bot_state)

	ideal_ending_points = set(game.state.get_all_border_territories(
		bot_state.war_focus
	)) - my_territories

	print("my_territories: ", my_territories, flush=True)
	print("starting points: ", path_starting_points, flush=True)
	starting_point_power = sum([game.state.territories[t[0]].troops for t in path_starting_points])
	print("starting point power:", starting_point_power, flush=True)
	enemy_territories_in_war_focus = bot_state.war_focus - my_territories
	print("enemy territories in war focus:", flush=True)
	for terr in enemy_territories_in_war_focus:
		print(terr, ", power: ", game.state.territories[terr].troops)
	war_focus_enemy_power = sum([game.state.territories[t].troops for t in enemy_territories_in_war_focus])
	print("war_focus_enemy_power:", war_focus_enemy_power, flush=True)

	if starting_point_power > 0.857 *war_focus_enemy_power + len(enemy_territories_in_war_focus): # Dont factor in troops left behind, ends up making this too unoptimistic because attacking with high numbers is very good
		bot_state.max_search_depth = 10000
		hamiltonian_warpath(path_starting_points, path_solutions)
	else:
		print("heuristic based check failed", flush=True)
		bot_state.chosen_attack_path = []
	sol = []
	# print("path solutions:", path_solutions,flush=True)
	print(f"found {len(path_solutions)}, potential solutions", flush=True)

	if len(path_solutions) > 0:

		most_ends_at_preferred_points = max([len([s_ for s_ in x if s_[-1] in ideal_ending_points]) for x in path_solutions])
		end_point_filtered = [p for p in path_solutions if len([s_ for s_ in p if s_[-1] in ideal_ending_points]) == most_ends_at_preferred_points]

		most_optimal_solution = max(end_point_filtered, key=lambda x:min(estimated_remaining_troops(game, s) for s in x))
		if min(estimated_remaining_troops(game, s) for s in most_optimal_solution) > 1:
			sol = [s_.copy() for s_ in most_optimal_solution]
		for sub_path in most_optimal_solution:
			print("starting power:", sub_path[0],game.state.territories[sub_path[0]].troops, flush=True)
			print("path power:", sub_path[1:], len(sub_path[1:]), sum([game.state.territories[p_].troops for p_ in sub_path[1:]]), flush=True)
			print("estimated remaining troops: ", estimated_remaining_troops(game, sub_path), flush=True)

	bot_state.chosen_attack_path = sol

def get_focuses(bot_state:BotState, game:Game):
	bot_state.war_focus = bot_state.region_capture_priority[0]
	bot_state.defense_focus = set([])
	for (region, next_region) in zip(bot_state.region_capture_priority[:-1], bot_state.region_capture_priority[1:]):
		bot_state.defense_focus.update(region)
		if controlling_region(game, region):
			bot_state.war_focus = next_region
		else:
			bot_state.war_focus = region
			break
	eliminate_check(game,bot_state)
	
def eliminate_check(game:Game, bot_state:BotState):
	my_territories = set(game.state.get_territories_owned_by(game.state.me.player_id))
	adjacent_to_me = adjacent_to_region(game, my_territories)
	for player in game.state.players.keys():
		if set(game.state.get_territories_owned_by(player)).issubset(adjacent_to_me):
			# if we are adjacent to all of this players territories we can probably just kill them.
			# drop everything and attack them
			bot_state.war_focus = set(game.state.get_territories_owned_by(player))
			bot_state.defense_focus = set([])
			break

def estimated_remaining_troops(game: Game, path:list[int]):
	# print("path in estimation:" , path, flush=True)
	attacker = game.state.territories[path[0]].troops
	defenders = [game.state.territories[t].troops for t in path[1:]]
	# print("attacker power: ", attacker)
	# print("defender powers: ", defenders, f"total {sum(defenders)}")
	# print(f"estimated remaining: {attacker - 0.857 * sum(defenders) - len(defenders)}")

	return attacker - 0.857 * sum(defenders) - len(defenders)



if __name__ == "__main__":
	main()