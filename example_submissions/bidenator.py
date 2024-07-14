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


from enum import Flag
class ContinentState(Flag):
    ENEMY    = 0
    FRIENDLY = 1
    CHANGED  = 2
    LOST   = CHANGED | ENEMY
    GAINED = CHANGED | FRIENDLY


# Stop requesting these a bajillion times every turn AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
sa_territories = set()
na_territories = set()
eurafrica_territories = set()


# We will store our enemy in the bot state.
class BotState():
    def __init__(self):
        self.enemy: Optional[int] = None

        self.defending_continents = []
        self.attacking_continent = 3

        self.SA_state = ContinentState.ENEMY
        self.NA_state = ContinentState.ENEMY
        self.EURAFRICA_state = ContinentState.ENEMY

        # This is an array of attacks to perform during
        # the attack stage. The following is an example
        # of what two potential attacks could look like:
        #     [
        #         [2, 8, 6, 1, 0],
        #         [7, 4]
        #     ]
        # The first element in the list is the starting
        # territory, and subsequent elements define the
        # chain of attack. Currently, there's no way to
        # specify how many troops to attack with...
        self.attacks = []


def main():
    
    # Get the game object, which will connect you to the engine and
    # track the state of the game.
    game = Game()
    bot_state = BotState()

    sa_territories = set(game.state.map.get_continents()[3])
    na_territories = set(game.state.map.get_continents()[0])
    america_territories = sa_territories | na_territories
    eurafrica_territories = set(game.state.map.get_continents()[1]) | set(game.state.map.get_continents()[4]) | set([22])
   
    # Respond to the engine's queries with your moves.
    while True:

        # Get the engine's query (this will block until you receive a query).
        query = game.get_next_query()
        my_territories = game.state.get_territories_owned_by(game.state.me.player_id)

        # for continent in bot_state.attacking_continents:
        if bot_state.attacking_continent in my_territories:
            bot_state.defending_continents.append(bot_state.attacking_continent)
            bot_state.attacking_continent = None # i think this works?    


        # If the state of South America hasn't
        # changed, reset the "changed" flag.
        bot_state.SA_state = update_continent_state(bot_state.SA_state, my_territories, sa_territories)
        bot_state.NA_state = update_continent_state(bot_state.NA_state, my_territories, na_territories)
        bot_state.EURAFRICA_state = update_continent_state(bot_state.EURAFRICA_state, my_territories, eurafrica_territories)

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
    """At the start of the game, you can claim a single unclaimed territory every turn 
    until all the territories have been claimed by players."""

    # Get unclaimed territories.
    unclaimed_territories = set(game.state.get_territories_owned_by(None))


    # these are the strategically important regions at the start
    regions = {
        "SA" :      sa_territories & unclaimed_territories,
        "SA_NEAR" : set([36,2,3,1,15,32,13,34,33]) & unclaimed_territories,
        "NA" :      na_territories & unclaimed_territories,
        "NA_NEAR" : set([30,10,21,31,29,9,12,27,18,20]) & unclaimed_territories
    }
    priorities = [regions["SA"], regions["SA_NEAR"], regions['NA']]

    for i in range(len(priorities)):
        if len(priorities[i]) > 0:
            selection = priorities[i].pop()
            return game.move_claim_territory(query, selection)

    my_territories = game.state.get_territories_owned_by(game.state.me.player_id)
    adjacent_territories = game.state.get_all_adjacent_territories(my_territories)


    # We will try to always pick new territories that are next to ones that we own,
    # or a random one if that isn't possible.

    # We can only pick from territories that are unclaimed and adjacent to us.
    available = list(set(unclaimed_territories) & set(adjacent_territories))
    if len(available) != 0:

        # We will pick the one with the most connections to our territories
        # this should make our territories clustered together a little bit.
        def count_adjacent_friendly(x: int) -> int:
            return len(set(my_territories) & set(game.state.map.get_adjacent_to(x)))

        selected_territory = sorted(available, key=lambda x: count_adjacent_friendly(x), reverse=True)[0]
    
    # Or if there are no such territories, we will pick just an unclaimed one with the greatest degree.
    else:
        selected_territory = sorted(unclaimed_territories, key=lambda x: len(game.state.map.get_adjacent_to(x)), reverse=True)[0]

    return game.move_claim_territory(query, selected_territory)


def handle_place_initial_troop(game: Game, bot_state: BotState, query: QueryPlaceInitialTroop) -> MovePlaceInitialTroop:
    """After all the territories have been claimed, you can place a single troop on one
    of your territories each turn until each player runs out of troops."""
    
    # critical_borders = [2,30,29]
    my_territories = set(game.state.get_territories_owned_by(game.state.me.player_id))
    border_territories = set(game.state.get_all_border_territories(
        game.state.get_territories_owned_by(game.state.me.player_id)
    ))

    enforcement_targets = set()

    if bot_state.SA_state & ContinentState.FRIENDLY:
        if 2 in my_territories:
            if 8 in my_territories and 3 in my_territories:
                enforcement_targets.update(set([3,8]))
            else:
                enforcement_targets.add(2)
        # if 36 in my_territories:
        #     enforcement_targets.add(36)
        # else:
        enforcement_targets.add(29)
        in_danger_territory = max(enforcement_targets, key=lambda x: threat(game,x))

        if threat(game, in_danger_territory) > 0:
            print(f"placing troops on {in_danger_territory}", flush=True)
            return game.move_place_initial_troop(query, in_danger_territory)

        for terr in enforcement_targets:
            if game.state.territories[terr].troops < 5:
                print(f"placing troops on {terr}", flush=True)
                return game.move_place_initial_troop(query, terr)

        # If none of our chokepoints are in danger, then we place units in the war for NA
        print("chokepoints are secure, fighting for NA", flush=True)
        na_borders = set([0,1,2,3,4,5,6,7]) & border_territories
        print(f"na borders: {na_borders}", flush=True)
        if len(na_borders) == 0:
            # if we have no territory in Na just put it on venezuela
            print("no territory in NA, placing units on venezuela", flush=True)
            return game.move_place_initial_troop(query, 30)
        
        in_danger_territory = max(na_borders, key=lambda x: threat(game,x))

        if threat(game, in_danger_territory) > 0:
            print(f"placing troops on {in_danger_territory}", flush=True)
            return game.move_place_initial_troop(query, in_danger_territory)

        for terr in na_borders:
            if game.state.territories[terr].troops < 5:
                print(f"placing troops on {terr}", flush=True)
                return game.move_place_initial_troop(query, terr)
        print("placing on a random NA border", flush=True)
        return game.move_place_initial_troop(query, na_borders.pop())
    else:
        sa_territories = set([30,29,31,28])
        my_sa_territories = sa_territories & my_territories

        if len(my_sa_territories) != 0:
            if 29 in my_territories:
                print("placing troops on 29", flush=True)
                return game.move_place_initial_troop(query, 29)
            elif 31 in my_territories:
                print("placing troops on 31", flush=True)
                return game.move_place_initial_troop(query, 31)
        # We will place troops along the territories on our border.
        print("my sa territories:", my_sa_territories, flush=True)
        border_sa_territories = border_territories & set([31,30,28,29])
        in_danger_territory = max(border_sa_territories, key=lambda x: threat(game,x))
        print(f"not in control of SA,, most in danger territory is {in_danger_territory}", flush=True)
        return game.move_place_initial_troop(query, in_danger_territory)

    raise Exception

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
    total_troops = game.state.me.troops_remaining
    distributions = defaultdict(lambda: 0)
    # We need to remember we have to place our matching territory bonus
    # if we have one.
    if len(game.state.me.must_place_territory_bonus) != 0:
        assert total_troops >= 2
        distributions[game.state.me.must_place_territory_bonus[0]] += 2
        total_troops -= 2


    

    my_territories = set(game.state.get_territories_owned_by(game.state.me.player_id))

    border_territories = set(game.state.get_all_border_territories(list(my_territories)))

    choke_points = []
    # If we've still got SA and NA, we can work on fortifying our chokes.
    if bot_state.SA_state & bot_state.NA_state & ContinentState.FRIENDLY:
        if 21 in my_territories:
            choke_points.append(21)
        else:
            choke_points.append(0)
        if 10 in my_territories:
            choke_points.append(10)
        else:
            choke_points.append(4)
        # if 36 in my_territories:
        #     choke_points.append(36)
        # else:
        choke_points.append(29)

        # If we get to this point it means we are probably already capable of killing the bad guys in na
        priority_choke_points = [c for c in choke_points if threat(game, c) > 0]
        if len(priority_choke_points) != 0:
            choke_points = priority_choke_points

        troops_per_territory = total_troops // len(choke_points)
        leftover_troops = total_troops % len(choke_points)
        for territory in choke_points:
            distributions[territory] += troops_per_territory
        distributions[choke_points[0]] += leftover_troops
        return game.move_distribute_troops(query, distributions)


    patch_territories = set()
    if bot_state.SA_state == ContinentState.LOST:
        patch_territories |= sa_territories
    if bot_state.NA_state == ContinentState.LOST:
        patch_territories |= na_territories
    # If we've lost SA or NA since our last turn,
    # we probably have some holes to patch up.
    if patch_territories != {}:
        enemy_territories = patch_territories - my_territories
        # We only need to consider friendly territories that
        # are adjacent to the territories we want to patch.
        friendly_territories = set(game.state.get_all_adjacent_territories(enemy_territories)) & border_territories
        if enemy_territories != {} and friendly_territories != {}:
            # We should probably check if holes need to be patched
            # when considering whether to turn in cards, as it's not
            # worth saving them for a rainy day if we're getting owned.
            paths = patch_holes(game, bot_state, friendly_territories, enemy_territories)

            # Now that we've found attack paths, we should check how
            # viable they are and distribute any troops as necessary.
            #


    # If we still have troops left over, we should
    # use them to try and fortify SA and NA.
    if bot_state.SA_state & ContinentState.FRIENDLY:

        if 2 in my_territories:
            choke_points.append(2)
        else:
            choke_points.append(30)
        if 36 in my_territories:
            choke_points.append(36)
        else:
            choke_points.append(29)
        
        enemy_na_territories = na_territories - my_territories
        my_na_territories = na_territories & my_territories
        my_na_borders = my_na_territories & border_territories

        if len(my_na_borders) != 0:

            # We are fighting for NA
            total_enemy_power_in_na = sum([game.state.territories[x].troops for x in enemy_na_territories])
            location_of_my_largest_stack_in_na = max(my_na_borders, key=lambda x: game.state.territories[x].troops)

            power_of_my_largest_stack_border_in_na = game.state.territories[location_of_my_largest_stack_in_na].troops
            
            if power_of_my_largest_stack_border_in_na < total_enemy_power_in_na *1.25 + 2 : # safety margin
                # for now we just stack absolutely everything onto this territory.
                distributions[location_of_my_largest_stack_in_na] += total_troops
                return game.move_distribute_troops(query, distributions)

        # If we get to this point it means we are probably already capable of killing the bad guys in na
        troops_per_territory = total_troops // len(choke_points)
        leftover_troops = total_troops % len(choke_points)
        for territory in choke_points:
            distributions[territory] += troops_per_territory
        distributions[choke_points[0]] += leftover_troops
        return game.move_distribute_troops(query, distributions)

    else:
        # we assume this is a fight for SA and not just 'patching holes'.
        # this code is very repetitive i know.

        enemy_sa_territories = sa_territories - my_territories
        my_sa_territories = sa_territories & my_territories
        my_sa_borders = my_sa_territories & border_territories
        if len(my_sa_borders) == 0:
            # this is grim, it means we have no territories in SA
            # stack on our largest stack of troops
            location_of_my_largest_stack = max(my_territories, key=lambda x: game.state.territories[x].troops)
            distributions[location_of_my_largest_stack] += total_troops
            return game.move_distribute_troops(query, distributions)
        if 29 in my_sa_territories:
            distributions[29] += total_troops
            return game.move_distribute_troops(query, distributions)
        elif 31 in my_sa_territories:
            distributions[31] += total_troops
            return game.move_distribute_troops(query, distributions)
        
        # Actually dont do any of this just stack one of these two states

        # my_na_border_territories = my_na_territories & border_territories
        total_enemy_power_in_sa = sum([game.state.territories[x].troops for x in enemy_sa_territories])

        location_of_my_largest_stack_in_sa = max(my_sa_borders, key=lambda x: game.state.territories[x].troops)
        power_of_my_largest_stack_border_in_sa = game.state.territories[location_of_my_largest_stack_in_sa].troops
        
        if power_of_my_largest_stack_border_in_sa < total_enemy_power_in_sa *1.25 + 2 : # safety margin
            # for now we just stack absolutely everything onto this territory.
            distributions[location_of_my_largest_stack_in_sa] += total_troops
            return game.move_distribute_troops(query, distributions)


        choke_points = my_sa_borders

        # If we get to this point it means we are probably already capable of killing the bad guys in sa
        troops_per_territory = total_troops // len(choke_points)
        leftover_troops = total_troops % len(choke_points)
        for territory in choke_points:
            distributions[territory] += troops_per_territory
        distributions[choke_points.pop()] += leftover_troops
        return game.move_distribute_troops(query, distributions)
    
    raise Exception


    # # We will equally distribute across border territories in the early game,
    # # but start doomstacking in the late game.
    # if len(game.state.recording) < 4000:
    #     troops_per_territory = total_troops // len(border_territories)
    #     leftover_troops = total_troops % len(border_territories)
    #     for territory in border_territories:
    #         distributions[territory] += troops_per_territory
    
    #     # The leftover troops will be put some territory (we don't care)
    #     distributions[border_territories[0]] += leftover_troops
    
    # else:
    #     my_territories = game.state.get_territories_owned_by(game.state.me.player_id)
    #     weakest_players = sorted(game.state.players.values(), key=lambda x: sum(
    #         [game.state.territories[y].troops for y in game.state.get_territories_owned_by(x.player_id)]
    #     ))

    #     for player in weakest_players:
    #         bordering_enemy_territories = set(game.state.get_all_adjacent_territories(my_territories)) & set(game.state.get_territories_owned_by(player.player_id))
    #         if len(bordering_enemy_territories) > 0:
    #             print("my territories", [game.state.map.get_vertex_name(x) for x in my_territories], flush=True)
    #             print("bordering enemies", [game.state.map.get_vertex_name(x) for x in bordering_enemy_territories], flush=True)
    #             print("adjacent to target", [game.state.map.get_vertex_name(x) for x in game.state.map.get_adjacent_to(list(bordering_enemy_territories)[0])], flush=True)
    #             selected_territory = list(set(game.state.map.get_adjacent_to(list(bordering_enemy_territories)[0])) & set(my_territories))[0]
    #             distributions[selected_territory] += total_troops
    #             break


    # return game.move_distribute_troops(query, distributions)

def handle_attack(game: Game, bot_state: BotState, query: QueryAttack) -> Union[MoveAttack, MoveAttackPass]:
    print("STARTING TURN ", len(game.state.recording), flush=True)
    war_focus = set()
    my_territories = set(game.state.get_territories_owned_by(game.state.me.player_id))

    def covers_war_focus(mega_path:set):
        return war_focus.issubset(mega_path | my_territories)

    def hamiltonian_warpath(current_paths:list[list[int]], solutions:list):
        all_nodes_in_paths = set()
        for p in current_paths:
            all_nodes_in_paths.update(set([p_ for p_ in p]))
        all_possible_neighbours = set()
        for p in current_paths:
            all_possible_neighbours.update(set(game.state.map.get_adjacent_to(p[-1])) & (war_focus - set(all_nodes_in_paths) - my_territories))
        if len(all_possible_neighbours) == 0:
            if covers_war_focus(all_nodes_in_paths):
                solutions.append([p.copy() for p in current_paths])
            return
        for p in current_paths:
            for neighbour in set(game.state.map.get_adjacent_to(p[-1])) & (war_focus - set(all_nodes_in_paths) - my_territories):
                p.append(neighbour)
                hamiltonian_warpath(current_paths, solutions)
                p.pop(-1)
    
    if bot_state.SA_state & ContinentState.FRIENDLY:
        if bot_state.NA_state & ContinentState.FRIENDLY:
            # war_focus = some other continent to attack next
            if bot_state.EURAFRICA_state & ContinentState.FRIENDLY:
                war_focus = set(game.state.map.get_continents()[5]) | set(game.state.map.get_continents()[2])
            else:
                war_focus = set(game.state.map.get_continents()[1]) | set(game.state.map.get_continents()[4]) | set([22])
            war_focus = set(range(41)) # attack all other continents
        else:
            war_focus = set(game.state.map.get_continents()[0]) # NA
    else:
        war_focus = set(game.state.map.get_continents()[3]) # SA

    # war_focus
    print("war focus: ", war_focus, flush=True)
    path_solutions = []
    # path_starting_points = [[t] for t in war_focus & my_territories if game.state.territories[t].troops > 3]
    path_starting_points = (set(game.state.get_all_adjacent_territories(war_focus)) | war_focus) & my_territories # Starting points dont need to be inside of the war focus
    path_starting_points = [[p] for p in path_starting_points]
    print("my_territories: ", my_territories, flush=True)
    print("starting points: ", path_starting_points, flush=True)
    # Do an initial check to see if we have enough troops
    enemy_territories_in_war_focus = war_focus - my_territories
    starting_point_power = sum([game.state.territories[t[0]].troops for t in path_starting_points])
    war_focus_enemy_power = sum([game.state.territories[t].troops for t in enemy_territories_in_war_focus])
    # num_troops_left_behind = len(enemy_territories_in_war_focus | set([t[0] for t in path_starting_points]))
    print("starting point power:", starting_point_power, flush=True)
    print("enemy territories in war focus:", enemy_territories_in_war_focus, flush=True)
    print("war_focus_enemy_power:", war_focus_enemy_power, flush=True)
    # print("num_troops_left_behind:", num_troops_left_behind, flush=True)
    if starting_point_power > war_focus_enemy_power: # Dont factor in troops left behind, ends up making this too unoptimistic because attacking with high numbers is very good
        hamiltonian_warpath(path_starting_points, path_solutions)
    else:
        print("heuristic based check failed", flush=True)
        return game.move_attack_pass(query)
    sol = []
    # print("path solutions:", path_solutions,flush=True)
    for s in path_solutions:
        found = True
        # print("one possible solution: ", s, flush=True)
        for sub_path in s:
            # print("starting power:", sub_path[0],game.state.territories[sub_path[0]].troops, flush=True)
            # print("path power:", sub_path[1:], len(sub_path[1:]), sum([game.state.territories[p_].troops for p_ in sub_path[1:]]), flush=True)
            # print("path validity:", game.state.territories[sub_path[0]].troops > sum([game.state.territories[t].troops for t in sub_path[1:]]), flush=True)

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
    print(game.state.territories[source].troops - 1, flush=True)
    return game.move_attack(query, source, target, min(3, game.state.territories[source].troops - 1))



def handle_attack_old(game: Game, bot_state: BotState, query: QueryAttack) -> Union[MoveAttack, MoveAttackPass]:
    """After the troop phase of your turn, you may attack any number of times until you decide to
    stop attacking (by passing). After a successful attack, you may move troops into the conquered
    territory. If you eliminated a player you will get a move to redeem cards and then distribute troops."""
    
    # new_handle_attack(game,bot_state,query)
    # We will attack someone.
    my_territories = set(game.state.get_territories_owned_by(game.state.me.player_id))
    border_territories = set(game.state.get_all_adjacent_territories(my_territories))
    my_sa_territories = sa_territories & my_territories
    enemy_sa_territories = sa_territories - my_territories

    if not bot_state.SA_state & ContinentState.FRIENDLY and len(my_sa_territories) > 0:
        # this is a fight for SA
        enemy_sa_territories = sa_territories - my_territories
        my_sa_borders = my_sa_territories & border_territories
        total_enemy_power = sum([game.state.territories[t].troops for t in enemy_sa_territories])

        print("FIGHTING FOR SA",flush=True)
        print(f"MY SA BORDERS: {my_sa_borders}",flush=True)
        print(f"sa_territories: {sa_territories}",flush=True)
        print(f"my_territories: {my_territories}",flush=True)
        print(f"enemy_sa_territories: {enemy_sa_territories}",flush=True)
        # location_of_largest_enemy_stack_in_sa = max(enemy_sa_territories, key=lambda x: game.state.territories[x].troops)
        # power_of_largest_enemy_stack_in_sa = game.state.territories[location_of_largest_enemy_stack_in_sa].troops

        # location_of_my_largest_stack_in_sa = max(my_sa_borders, key=lambda x: game.state.territories[x].troops)

        strong_territories = sorted(my_sa_borders, key=lambda x: game.state.territories[x].troops, reverse=True)
        for source in strong_territories:
            print(f"STRONG TERRITORY: {source}", flush=True)
            attackable_territories = set(game.state.map.get_adjacent_to(source)) & enemy_sa_territories
            print(f"ATTACKABLE TERRITORIES: {attackable_territories}", flush=True)
            for target in sorted(attackable_territories, key=lambda x: game.state.territories[x].troops, reverse=True):
                # we attack the strongest attackable territory that we can beat
                print(f"POTENTIAL TARGET: {target}", flush=True)
                print(f"attackability: {game.state.territories[target].troops * 1.25 + 2} vs {game.state.territories[source].troops}", flush=True)
                if game.state.territories[target].troops * 1.25 + 2 < game.state.territories[source].troops:
                    print(f"ATTACKING {target}", flush=True)
                    return game.move_attack(query, source, target, min(3, game.state.territories[source].troops - 1))

        print("ENEMIES TOO STRONG",flush=True)
        # we cannot beat any enemy stack with any of our target stacks, then we just chill.
        return game.move_attack_pass(query)

    if bot_state.SA_state & ContinentState.FRIENDLY and not bot_state.NA_state & ContinentState.FRIENDLY:
        print("ATTACKING NA", flush=True)
        na_territories = set(game.state.map.get_continents()[0])
        my_na_territories =  my_territories & na_territories
        enemy_sa_territories = na_territories - my_territories


        if 2 in my_territories:
            # we control 2
            return game.move_attack_pass(query)

            pass
            # if 3 in my_territories and 8 in my_territories:
            #     pass
            # else:
            #     if game.state.territories[2].troops > sum()
            #     pass
            #     # we control 8 and 3
            #     if 1 in my_territories and 6 in my_territories and 7 in my_territories:
            #         pass
            #     else:

            #         pass
            
            # elif not 3 in my_territories and not 8 in my_territories:
            #     # we are attacking both 8 and 3 from 2

            # elif 3 in my_territories and not 8 in my_territories:
            #     # we are attacking 8 from 2 and 3
            # elif not 3 in my_territories and 8 in my_territories:
            #     # we are attacking 3 from 8 and 2

        elif game.state.territories[30].troops > game.state.territories[2].troops * 1.25 + 2:
            return game.move_attack(query, 30, 2, min(3, game.state.territories[30].troops - 1))
        else:
            # we cannot attack na yet, so we wait
            return game.move_attack_pass(query)

    def attack_weakest(territories: list[int]) -> Optional[MoveAttack]:
        # We will attack the weakest territory from the list.
        territories = sorted(territories, key=lambda x: game.state.territories[x].troops)
        for candidate_target in territories:
            candidate_attackers = sorted(list(set(game.state.map.get_adjacent_to(candidate_target)) & set(my_territories)), key=lambda x: game.state.territories[x].troops, reverse=True)
            for candidate_attacker in candidate_attackers:
                if game.state.territories[candidate_attacker].troops > 1:
                    return game.move_attack(query, candidate_attacker, candidate_target, min(3, game.state.territories[candidate_attacker].troops - 1))


    if len(game.state.recording) < 4000:
        # We will check if anyone attacked us in the last round.
        new_records = game.state.recording[game.state.new_records:]
        enemy = None
        for record in new_records:
            match record:
                case MoveAttack() as r:
                    if r.defending_territory in set(my_territories):
                        enemy = r.move_by_player

        # If we don't have an enemy yet, or we feel angry, this player will become our enemy.
        if enemy != None:
            if bot_state.enemy == None or random.random() < 0.05:
                bot_state.enemy = enemy
        
        # If we have no enemy, we will pick the player with the weakest territory bordering us, and make them our enemy.
        else:
            weakest_territory = min(border_territories, key=lambda x: game.state.territories[x].troops)
            bot_state.enemy = game.state.territories[weakest_territory].occupier
            
        # We will attack their weakest territory that gives us a favourable battle if possible.
        enemy_territories = list(set(border_territories) & set(game.state.get_territories_owned_by(enemy)))
        move = attack_weakest(enemy_territories)
        if move != None:
            return move
        
        # Otherwise we will attack anyone most of the time.
        if random.random() < 0.8:
            move = attack_weakest(border_territories)
            if move != None:
                return move

    # In the late game, we will attack anyone adjacent to our strongest territories (hopefully our doomstack).
    else:
        kill_deathstack(game)
        strongest_territories = sorted(my_territories, key=lambda x: game.state.territories[x].troops, reverse=True)
        for territory in strongest_territories:
            move = attack_weakest(list(set(game.state.map.get_adjacent_to(territory)) - set(my_territories)))
            if move != None:
                return move

    return game.move_attack_pass(query)


def handle_troops_after_attack(game: Game, bot_state: BotState, query: QueryTroopsAfterAttack) -> MoveTroopsAfterAttack:
    """After conquering a territory in an attack, you must move troops to the new territory."""
    
    # First we need to get the record that describes the attack, and then the move that specifies
    # which territory was the attacking territory.
    record_attack = cast(RecordAttack, game.state.recording[query.record_attack_id])
    move_attack = cast(MoveAttack, game.state.recording[record_attack.move_attack_id])

    # We will always move the maximum number of troops we can.

    # theoretical_game 

    # if move_attack.attacking_territory == 29 or move_attack.attacking_territory == 30:
    #     if bot_state.controlling_SA and move_attack.defending_territory in [31,28,30,29]:
    #         return game.move_troops_after_attack(query, min(move_attack.attacking_troops, game.state.territories[move_attack.attacking_territory].troops - 1))
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

def update_continent_state(old_state:ContinentState, my_territories:set, continent_territories:set) -> ContinentState:
    current_state = ContinentState.FRIENDLY if set(continent_territories).issubset(my_territories) else ContinentState.ENEMY
    # If we haven't taken or lost the continent
    # since the last turn, reset the "changed" flag.
    old_state &= ~ContinentState.CHANGED
    if old_state == current_state:
        return old_state

    # Otherwise, flip the state and set the "changed" flag.
    return (old_state ^ (ContinentState.ENEMY | ContinentState.FRIENDLY)) | ContinentState.CHANGED

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


def find_connected_components(graph:dict[int, set]) -> list[set[int]]:
    """Find the connected components of the given graph.
    We use the DSU (disjoint set union) algorithm."""

    parents = dict((vertex, vertex) for vertex in graph);
    connected_components = dict()

    # Iterate upwards through the graph until
    # we find a vertex that is its own parent.
    # This is the root of the connected component.
    def find_root(vertex):
        if parents[vertex] != vertex:
            parents[vertex] = find_root(parents[vertex])
        return parents[vertex]

    # For each edge in the graph, set the parent of the starting
    # vertex to be the parent of the ending vertex. This essentially
    # merges connected vertices into one connected component.
    for start in graph:
        for end in graph[start]:
            # Don't double count edges!
            if start < end:
                parents[find_root(start)] = find_root(end)

    # Add each vertex to its connected component.
    for vertex in graph:
        current_root = find_root(parents[vertex])
        if current_root in connected_components:
            connected_components[current_root].add(vertex)
        else:
            connected_components[current_root] = {current_root, vertex}

    return [set(connected_components[component]) for component in connected_components]


def patch_holes(game:Game, bot_state:BotState, friendly_vertices:set[int], enemy_vertices:set[int]) -> list[list[int]]:
    """Identify any holes in a particular continent
    and find good paths of attack to patch them."""

    full_vertices = friendly_vertices | enemy_vertices
    # This is the full subgraph edges between only
    # the friendly and enemy vertices of interest.
    full_graph = dict((start, set(game.state.map.get_adjacent_to(start)) & full_vertices) for start in full_vertices)
    # Most of the time though, it will be quicker to search
    # through the subgraph of edges between enemy vertices.
    enemy_graph = dict((start, full_graph[start] & enemy_vertices) for start in enemy_vertices)
    # Keep track of any "endpoints", that is,
    # territories with only one connection.
    enemy_endpoints = set(vertex for vertex in enemy_vertices if len(enemy_graph[vertex]) == 1)

    # If this continent has been attacked from multiple angles,
    # we may have several connected components to reclaim.
    connected_components = find_connected_components(enemy_graph)

    # We've found the connected components, now we need a battle plan!
    # The following procedure should be performed for each connected component.
    #     1. Figure out a starting point. This should be our largest army
    #        bordering an enemy node, prioritizing those next to endpoints.
    #
    #     2. While there are unvisited nodes remaining, choose our next
    #        node to be the one with the fewest positive connections to
    #        nodes we haven't visited. If we see multiple nodes with one
    #        or zero connections, we'll need to create a splitting point.
    #
    #     3. Repeat the previous step starting at each splitting point.
    # The result of this process is a list of (possibly fragmented) paths
    # that visit every node in the connected component. While there are no
    # doubt smarter ways to do this, we expect enemies to usually take linear
    # paths through our territory, ending either randomly or before an army.

    # Find the friendly territories with the largest armies.
    maximal_vertices = set()
    max_army_size = 1
    for vertex in friendly_vertices:
        cur_army_size = game.state.territories[vertex].troops
        if cur_army_size < max_army_size:
            continue
        elif cur_army_size == max_army_size:
            maximal_vertices.add(vertex)
        else:
            maximal_vertices = set(vertex)
            max_army_size = cur_army_size

    paths = []
    # Find an attack path through each connected component.
    for component in connected_components:
        cur_path = []

        # Step 1: Figure out a starting point.
        adjacent_vertices = maximal_vertices & full_graph[enemy_endpoints & component]
        # We should also find which of these are next to endpoints.
        if adjacent_vertices != {}:
            maximal_vertices = adjacent_vertices
        # If we still have multiple candidates, just choose
        # a "random" one. It might be better to prioritize
        # starting locations we've already chosen, but this
        # probably wouldn't be a significant improvement.
        cur_path.append(maximal_vertices.pop())

        # We need to use the full graph to find the first enemy
        # vertex, but after that we'll only need the enemy graph.
        # We should also choose any endpoints here if we can.
        adjacent_vertices = full_graph[cur_path[-1]] & component
        # Add any vertex with a minimal number of edges.
        splitting_points = {(cur_path[-1], min(adjacent_vertices, key=lambda v: len(enemy_graph[v])))}

        # Step 3: Repeat the process for each splitting point.
        while len(splitting_points) > 0:
            cur_path = list(splitting_points.pop())
            # This is pretty gross lol
            cur_path_set = set(cur_path)

            # Step 2: Find a path through the connected component.
            while (adjacent_vertices := enemy_graph[cur_path[-1]] - cur_path_set) != {}:
                # Find an adjacent vertex with a minimal but
                # positive number of edges to unvisited nodes.
                min_num_edges = len(game.state.territories)
                next_vertex = None
                for vertex in adjacent_vertices:
                    cur_num_edges = len(enemy_graph[vertex] - cur_path_set)
                    if 0 < cur_num_edges < min_num_edges:
                        # Add the previous vertex as a potential splitting point.
                        splitting_points.add((cur_path[-1], next_vertex))
                        # Update the next vertex.
                        next_vertex = vertex
                        min_edges = cur_num_edges

                    # If we have no chance of visiting a vertex, we
                    # should add it as a potential splitting point.
                    else:
                        splitting_points.add((cur_path[-1], vertex))

                # If every node was an endpoint, just add a random one.
                if next_vertex is None:
                    next_vertex = adjacent_vertices.pop()

                # Add the new node to the path and continue on.
                cur_path.append(next_vertex)
                cur_path_set.add(next_vertex)
                # If this node was previously added as a splitting
                # point, we should remove it from the set.
                splitting_points = {point for point in splitting_points if not point[1] == next_vertex}

            # Add the path to our list.
            paths.append(cur_path)

        # Now that we're done with this connected component,
        # we can remove all of its endpoints from our set.
        enemy_endpoints.discard(cur_endpoints)

    return paths


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





if __name__ == "__main__":
    main()