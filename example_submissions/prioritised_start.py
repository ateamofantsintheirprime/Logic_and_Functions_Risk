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
    def __init__(self):
        self.enemy: Optional[int] = None
        self.focus_continent: Optional[str] = None
        self.controlling_australia = False

def main():
    
    # Get the game object, which will connect you to the engine and
    # track the state of the game.
    game = Game()
    bot_state = BotState()
   
    # Respond to the engine's queries with your moves.
    while True:

        # Get the engine's query (this will block until you receive a query).
        query = game.get_next_query()

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

    
    """ The decisionmaking for claiming territories follows this:
    
        1. Pick a focus continent (Prioritise AU and then SA):
            1.1. if they're both pretty free, focus AU.
            1.2. if only one is free, focus that one.
            1.3. if and only if neither are free, then we focus NA 

        2. Claim territories as per focus continent:
            2.1. Claim as much territory as possible around that continent.
            2.2. Once it's fully claimed, try and claim whichever is more free out of AU SA or NA
            2.3. once those are fully claimed, just claim randomly.
        
        3. Stack units to protect the focus continent.
            3.1 If there is a large stack on the continent:
                Stack next to them until we are 3-4 + that size
            3.2 If there is a large stack close outside the continent:
                Stack at the chokepoint nearest to it until we are 3-4+ that size
            3.2 If there is both a large stack at the entrance and a large stack inside the continent:
                Change focus continents
    """

    # Get unclaimed territories.
    unclaimed_territories = set(game.state.get_territories_owned_by(None))


    # these are the strategically important regions at the start
    regions = {
        "AU" :      set([40,39,41,38]) & unclaimed_territories,
        "AU_NEAR" : set([24,17,18,25]) & unclaimed_territories,
        "SA" :      set([31,30,28,30]) & unclaimed_territories,
        "SA_NEAR" : set([36,2,3,1,15,32,13,34,33]) & unclaimed_territories,
        "NA" :      set([0,1,2,3,4,5,6,7]) & unclaimed_territories,
        "NA_NEAR" : set([30,10,21,31,29,9,12,27,18,20]) & unclaimed_territories
    }

    if bot_state.focus_continent == None:
        if len(regions["AU"]) >= 2:
            bot_state.focus_continent = "AU"
        elif len(regions["SA"]) >= 2:
            bot_state.focus_continent = "SA"
        elif len(regions["NA"]) >= 5:
            bot_state.focus_continent = "NA"

    match bot_state.focus_continent:
        case "AU":
            priorities = [regions["AU"], regions["AU_NEAR"], regions["SA"], regions['NA']]
        case "SA":
            priorities = [regions["SA"], regions["SA_NEAR"], regions["AU"], regions['NA']]
        case "NA":
            priorities = [regions["NA"], regions["NA_NEAR"], regions["SA"], regions['AU']]

    # print(f"""
    #     Focus continent: {bot_state.focus_continent}
    #     Available territories:
    #         1st priority: {priorities[0]}
    #         2nd priority: {priorities[1]}
    #         3rd priority: {priorities[2]}
    #         4th priority: {priorities[3]}
    # """, flush=True)

    for i in range(len(priorities)):
        if len(priorities[i]) > 0:
            selection = priorities[i].pop()
            print(f"Claiming: {selection}", flush=True)
            return game.move_claim_territory(query, selection)
    selection = unclaimed_territories.pop()
    print(f"No priority territories available, claiming {selection} randomly lol")
    # If all the priority regions are claimed just punt it randomly lol
    return game.move_claim_territory(query, selection)


def handle_place_initial_troop(game: Game, bot_state: BotState, query: QueryPlaceInitialTroop) -> MovePlaceInitialTroop:
    """After all the territories have been claimed, you can place a single troop on one
    of your territories each turn until each player runs out of troops."""
    
    # if we control all of australia, reinforce the border.
    my_territories = set(game.state.get_territories_owned_by(game.state.me.player_id))
    au_territories = set([40,39,41,38])
    if au_territories.issubset(my_territories):
        print("australia is under my control! reinforcing!", flush=True)
        if 24 in my_territories:
            return game.move_place_initial_troop(query, 24)
        else:
            return game.move_place_initial_troop(query, 40)
    
    # if we dont, stack next to the guy who's contesting us
    my_au_territories = au_territories & my_territories

    my_border_au_territories = game.state.get_all_border_territories(list(my_au_territories))
    
    for border_au_terri in my_border_au_territories:
        if threat(game, border_au_terri) * 1.25 + 2 > game.state.territories[border_au_terri].troops:
            print(f"this freak next to {border_au_terri} is too scary! stacking more!",flush=True)
            return game.move_place_initial_troop(query, border_au_terri)

    my_strongest_au_territory = max(my_au_territories, key=lambda x: game.state.territories[x].troops)

    # my_territories = game.state.get_territories_owned_by(game.state.me.player_id)
    # print(f"troll random stack!! this hsould never be printing!", flush=True)
    return game.move_place_initial_troop(query, my_strongest_au_territory)


def handle_redeem_cards(game: Game, bot_state: BotState, query: QueryRedeemCards) -> MoveRedeemCards:
    """After the claiming and placing initial troops phases are over, you can redeem any
    cards you have at the start of each turn, or after killing another player."""

    # Redeem as many cards as we can.
    card_sets: list[Tuple[CardModel, CardModel, CardModel]] = []
    cards_remaining = game.state.me.cards.copy()

    if query.cause == "turn_started":
        card_set = game.state.get_card_set(cards_remaining)
        while card_set != None:
            card_sets.append(card_set)
            cards_remaining = [card for card in cards_remaining if card not in card_set]
            card_set = game.state.get_card_set(cards_remaining)

    elif query.cause == "player_eliminated":
        while len(cards_remaining) >= 5:
            card_set = game.state.get_card_set(cards_remaining)
            # According to the pigeonhole principle, we should always be able to make a set
            # of cards if we have at least 5 cards.
            assert card_set != None
            card_sets.append(card_set)
            cards_remaining = [card for card in cards_remaining if card not in card_set]
            
    
    return game.move_redeem_cards(query, [(x[0].card_id, x[1].card_id, x[2].card_id) for x in card_sets])

def handle_distribute_troops(game: Game, bot_state: BotState, query: QueryDistributeTroops) -> MoveDistributeTroops:
    """After you redeem cards (you may have chosen to not redeem any), you need to distribute
    all the troops you have available across your territories. This can happen at the start of
    your turn or after killing another player.
    """

    # We will distribute troops across our border territories.
    total_troops = game.state.me.troops_remaining
    distributions = defaultdict(lambda: 0)
    border_territories = game.state.get_all_border_territories(
        game.state.get_territories_owned_by(game.state.me.player_id)
    )

    # We need to remember we have to place our matching territory bonus
    # if we have one.
    if len(game.state.me.must_place_territory_bonus) != 0:
        assert total_troops >= 2
        distributions[game.state.me.must_place_territory_bonus[0]] += 2
        total_troops -= 2


    # We will equally distribute across border territories in the early game,
    # but start doomstacking in the late game.
    if len(game.state.recording) < 4000:
        troops_per_territory = total_troops // len(border_territories)
        leftover_troops = total_troops % len(border_territories)
        for territory in border_territories:
            distributions[territory] += troops_per_territory
    
        # The leftover troops will be put some territory (we don't care)
        distributions[border_territories[0]] += leftover_troops
    
    else:
        my_territories = game.state.get_territories_owned_by(game.state.me.player_id)
        weakest_players = sorted(game.state.players.values(), key=lambda x: sum(
            [game.state.territories[y].troops for y in game.state.get_territories_owned_by(x.player_id)]
        ))

        for player in weakest_players:
            bordering_enemy_territories = set(game.state.get_all_adjacent_territories(my_territories)) & set(game.state.get_territories_owned_by(player.player_id))
            if len(bordering_enemy_territories) > 0:
                # print("my territories", [game.state.map.get_vertex_name(x) for x in my_territories])
                # print("bordering enemies", [game.state.map.get_vertex_name(x) for x in bordering_enemy_territories])
                # print("adjacent to target", [game.state.map.get_vertex_name(x) for x in game.state.map.get_adjacent_to(list(bordering_enemy_territories)[0])])
                selected_territory = list(set(game.state.map.get_adjacent_to(list(bordering_enemy_territories)[0])) & set(my_territories))[0]
                distributions[selected_territory] += total_troops
                break


    return game.move_distribute_troops(query, distributions)


def handle_attack(game: Game, bot_state: BotState, query: QueryAttack) -> Union[MoveAttack, MoveAttackPass]:
    """After the troop phase of your turn, you may attack any number of times until you decide to
    stop attacking (by passing). After a successful attack, you may move troops into the conquered
    territory. If you eliminated a player you will get a move to redeem cards and then distribute troops."""
    
    # Attack anyone.
    my_territories = game.state.get_territories_owned_by(game.state.me.player_id)
    def attack_if_possible(territories: list[int]):
        for candidate_target in territories:
            candidate_attackers = list(set(game.state.map.get_adjacent_to(candidate_target)) & set(my_territories))
            for candidate_attacker in candidate_attackers:
                if game.state.territories[candidate_attacker].troops > 1:
                    return game.move_attack(query, candidate_attacker, candidate_target, min(3, game.state.territories[candidate_attacker].troops - 1))

    bordering_territories = game.state.get_all_adjacent_territories(my_territories)
    attack = attack_if_possible(bordering_territories)
    if attack:
        return attack
    else:
        return game.move_attack_pass(query)


def handle_troops_after_attack(game: Game, bot_state: BotState, query: QueryTroopsAfterAttack) -> MoveTroopsAfterAttack:
    """After conquering a territory in an attack, you must move troops to the new territory."""
    
    # First we need to get the record that describes the attack, and then the move that specifies
    # which territory was the attacking territory.
    record_attack = cast(RecordAttack, game.state.recording[query.record_attack_id])
    move_attack = cast(MoveAttack, game.state.recording[record_attack.move_attack_id])

    # We will always move the maximum number of troops we can.
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

    # my_territories = game.state.get_territories_owned_by(game.state.me.player_id)
    # border_territories = game.state.get_all_border_territories(my_territories)

    # non_border_territories = list(set(my_territories).difference(set(border_territories)))
    
    # if len(non_border_territories) == 0:
    #     return game.move_fortify_pass(query) # this is grim
    
    # most_troops_territory = max(non_border_territories, key=lambda x: game.state.territories[x].troops)
    # print("border territories: ",border_territories)
    # print("most_troops_territory neighbours: ",game.state.map.get_adjacent_to(most_troops_territory))

    # fort_territories = fortifiable_territories(game,most_troops_territory)

    # print("fortifiable territories: ",fort_territories)

    # fortifiable_border_territories = set(border_territories) & set(fort_territories)
    
    # print("fortifiable border territories: ",fortifiable_border_territories)

    # most_threatened_fortifiable_territory = max(fortifiable_border_territories,key=lambda x: threat(game,x))
    # return game.move_fortify(query, most_troops_territory, most_threatened_fortifiable_territory, game.state.territories[most_troops_territory].troops - 1)
    
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
        print(f"fortifying from {shortest_path[0]} to {shortest_path[1]}", flush=True)
        return game.move_fortify(query, shortest_path[0], shortest_path[1], game.state.territories[most_troops_territory].troops - 1)
    else:
        print("not fortifying", flush=True)
        return game.move_fortify_pass(query)


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


def threat(game:Game, victim:int):
    threat = 0
    for neighbour_id in game.state.map.get_adjacent_to(victim):
        if game.state.territories[neighbour_id].occupier != game.state.me.player_id:
            threat += min(0,game.state.territories[neighbour_id].troops - 1)
    return threat
    # This is oversimplified and does not account for cards


def player_continents(game:Game):
    player_ids = [p for p in game.state.players.keys() if p != game.state.me.player_id]

    player_continents = {
        p_id : [
            c for c in game.state.map.get_continents().keys() \
            if set(game.state.map.get_continents()[c]).issubset(game.state.get_territories_owned_by(p_id))
        ] for p_id in player_ids
    } # This is horrifically bad code
    return player_continents

if __name__ == "__main__":
    main()