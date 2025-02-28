import time
import os
import random

from spirecomm.spire.game import Game
from spirecomm.spire.character import Intent, PlayerClass
import spirecomm.spire.card
from spirecomm.spire.screen import RestOption
from spirecomm.communication.action import *
from spirecomm.ai.priorities import *
from prompt import get_prompt, ask_deepseek
from utilities.voice import speak_async

def log(msg, attr=""):
    msg = str(msg)
    log_path = f"D:\\DeepSpire\\deepspire\\log_{attr}.txt"
    
    # if log file does not exist, create it
    if not os.path.exists(log_path):
        with open(log_path, "w", encoding="UTF-8") as f:
            pass 
          
    with open(log_path, "a", encoding="UTF-8") as f:
        f.write(msg + "\n")



def remove_redundant_keys(obj):
    if isinstance(obj, dict):
        for key in list(obj.keys()):
            if key == "uuid":
                obj.pop(key)
            # Neglect the default values
            elif key == "exhausts" and obj[key] == False:
                obj.pop(key)
            elif key == "upgrades" and obj[key] == 0:
                obj.pop(key)
            elif key == "ethereal" and obj[key] == False:
                obj.pop(key)

            else:
                remove_redundant_keys(obj[key])
    elif isinstance(obj, list):
        for item in obj:
            remove_redundant_keys(item)

def parse_tag(key, text):
    # Find content between <key> and </key>
    start_tag = "<" + key + ">"
    end_tag = "</" + key + ">"
    start = text.find(start_tag)
    end = text.find(end_tag)
    if start == -1 or end == -1:
        return ""
    return text[start + len(start_tag):end]

def simplify_json(json_obj):
    # The uuids of cards are not needed
    remove_redundant_keys(json_obj)
    # Remove ["json_state"]["map"] because it's too big
    json_obj["json_state"].pop("map")

    if "combat_state" in json_obj["json_state"]:
        # draw_pile + discard_pile + exhauset_pile = deck, so remove the deck to save tokens
        json_obj["json_state"].pop("deck")
    if "choice_list" in json_obj["json_state"] and len(json_obj["json_state"]["choice_list"]) == 1:
        # Have no choice, simplify the input to save tokens
        json_obj["json_state"].pop("deck")    
    return json_obj


class SimpleAgent:

    def __init__(self, chosen_class=PlayerClass.THE_SILENT):
        self.game = Game()
        self.errors = 0
        self.choose_good_card = False
        self.skipped_cards = False
        self.visited_shop = False
        self.map_route = []
        self.chosen_class = chosen_class
        self.priorities = Priority()
        self.change_class(chosen_class)

        self.silu = "<第一次交互，暂无已有思路>"

    def change_class(self, new_class):
        self.chosen_class = new_class
        if self.chosen_class == PlayerClass.THE_SILENT:
            self.priorities = SilentPriority()
        elif self.chosen_class == PlayerClass.IRONCLAD:
            self.priorities = IroncladPriority()
        elif self.chosen_class == PlayerClass.DEFECT:
            self.priorities = DefectPowerPriority()
        else:
            self.priorities = random.choice(list(PlayerClass))

    def handle_error(self, error):
        raise Exception(error)

    def get_next_action_in_game(self, game_state):
        try:
            state_json = game_state.to_json()
            state_json = simplify_json(state_json)
            
            if state_json["json_state"]["screen_type"] == "NONE":
                emph = {"当前手牌": state_json["json_state"]["combat_state"]["hand"]}
            else:
                emph = None
            prompt = get_prompt(self.silu, state_json, emph=emph)
            log("Prompt: " + prompt, "deepseek")
            response = ask_deepseek(prompt)
            log("Response: " + response, "deepseek")

            # parse out <command> </command> and <silu> </silu> and <comment> </comment>
            command = parse_tag("command", response)
            log(command, "command")
            silu = parse_tag("silu", response)
            log(silu, "silu")
            comment = parse_tag("comment", response)
            log(comment, "comment")

            self.silu = silu
            speak_async(comment)

            command_parts = command.split(" ")
            if command_parts[0] == "play":
                if len(command_parts) == 3:
                    generated_target = True
                else:
                    generated_target = False
                card_id = int(command_parts[1])
                if state_json["json_state"]["combat_state"]["hand"][card_id - 1].has_target:
                    need_target = True
                else:
                    need_target = False
                
                if need_target and not generated_target:
                    command_parts.append("0")
                elif not need_target and generated_target:
                    command_parts.pop()
                command = " ".join(command_parts)

            return Action(command=command)

        except Exception as e:
            log(e)
            log("Will use default AI.")

        self.game = game_state
        #time.sleep(0.07)
        if self.game.choice_available:
            return self.handle_screen()
        if self.game.proceed_available:
            return ProceedAction()
        if self.game.play_available:
            if self.game.room_type == "MonsterRoomBoss" and len(self.game.get_real_potions()) > 0:
                potion_action = self.use_next_potion()
                if potion_action is not None:
                    return potion_action
            return self.get_play_card_action()
        if self.game.end_available:
            return EndTurnAction()
        if self.game.cancel_available:
            return CancelAction()

    def get_next_action_out_of_game(self):
        return StartGameAction(self.chosen_class)

    def is_monster_attacking(self):
        for monster in self.game.monsters:
            if monster.intent.is_attack() or monster.intent == Intent.NONE:
                return True
        return False

    def get_incoming_damage(self):
        incoming_damage = 0
        for monster in self.game.monsters:
            if not monster.is_gone and not monster.half_dead:
                if monster.move_adjusted_damage is not None:
                    incoming_damage += monster.move_adjusted_damage * monster.move_hits
                elif monster.intent == Intent.NONE:
                    incoming_damage += 5 * self.game.act
        return incoming_damage

    def get_low_hp_target(self):
        available_monsters = [monster for monster in self.game.monsters if monster.current_hp > 0 and not monster.half_dead and not monster.is_gone]
        best_monster = min(available_monsters, key=lambda x: x.current_hp)
        return best_monster

    def get_high_hp_target(self):
        available_monsters = [monster for monster in self.game.monsters if monster.current_hp > 0 and not monster.half_dead and not monster.is_gone]
        best_monster = max(available_monsters, key=lambda x: x.current_hp)
        return best_monster

    def many_monsters_alive(self):
        available_monsters = [monster for monster in self.game.monsters if monster.current_hp > 0 and not monster.half_dead and not monster.is_gone]
        return len(available_monsters) > 1

    def get_play_card_action(self):
        playable_cards = [card for card in self.game.hand if card.is_playable]
        zero_cost_cards = [card for card in playable_cards if card.cost == 0]
        zero_cost_attacks = [card for card in zero_cost_cards if card.type == spirecomm.spire.card.CardType.ATTACK]
        zero_cost_non_attacks = [card for card in zero_cost_cards if card.type != spirecomm.spire.card.CardType.ATTACK]
        nonzero_cost_cards = [card for card in playable_cards if card.cost != 0]
        aoe_cards = [card for card in playable_cards if self.priorities.is_card_aoe(card)]
        if self.game.player.block > self.get_incoming_damage() - (self.game.act + 4):
            offensive_cards = [card for card in nonzero_cost_cards if not self.priorities.is_card_defensive(card)]
            if len(offensive_cards) > 0:
                nonzero_cost_cards = offensive_cards
            else:
                nonzero_cost_cards = [card for card in nonzero_cost_cards if not card.exhausts]
        if len(playable_cards) == 0:
            return EndTurnAction()
        if len(zero_cost_non_attacks) > 0:
            card_to_play = self.priorities.get_best_card_to_play(zero_cost_non_attacks)
        elif len(nonzero_cost_cards) > 0:
            card_to_play = self.priorities.get_best_card_to_play(nonzero_cost_cards)
            if len(aoe_cards) > 0 and self.many_monsters_alive() and card_to_play.type == spirecomm.spire.card.CardType.ATTACK:
                card_to_play = self.priorities.get_best_card_to_play(aoe_cards)
        elif len(zero_cost_attacks) > 0:
            card_to_play = self.priorities.get_best_card_to_play(zero_cost_attacks)
        else:
            # This shouldn't happen!
            return EndTurnAction()
        if card_to_play.has_target:
            available_monsters = [monster for monster in self.game.monsters if monster.current_hp > 0 and not monster.half_dead and not monster.is_gone]
            if len(available_monsters) == 0:
                return EndTurnAction()
            if card_to_play.type == spirecomm.spire.card.CardType.ATTACK:
                target = self.get_low_hp_target()
            else:
                target = self.get_high_hp_target()
            return PlayCardAction(card=card_to_play, target_monster=target)
        else:
            return PlayCardAction(card=card_to_play)

    def use_next_potion(self):
        for potion in self.game.get_real_potions():
            if potion.can_use:
                if potion.requires_target:
                    return PotionAction(True, potion=potion, target_monster=self.get_low_hp_target())
                else:
                    return PotionAction(True, potion=potion)

    def handle_screen(self):
        if self.game.screen_type == ScreenType.EVENT:
            if self.game.screen.event_id in ["Vampires", "Masked Bandits", "Knowing Skull", "Ghosts", "Liars Game", "Golden Idol", "Drug Dealer", "The Library"]:
                return ChooseAction(len(self.game.screen.options) - 1)
            else:
                return ChooseAction(0)
        elif self.game.screen_type == ScreenType.CHEST:
            return OpenChestAction()
        elif self.game.screen_type == ScreenType.SHOP_ROOM:
            if not self.visited_shop:
                self.visited_shop = True
                return ChooseShopkeeperAction()
            else:
                self.visited_shop = False
                return ProceedAction()
        elif self.game.screen_type == ScreenType.REST:
            return self.choose_rest_option()
        elif self.game.screen_type == ScreenType.CARD_REWARD:
            return self.choose_card_reward()
        elif self.game.screen_type == ScreenType.COMBAT_REWARD:
            for reward_item in self.game.screen.rewards:
                if reward_item.reward_type == RewardType.POTION and self.game.are_potions_full():
                    continue
                elif reward_item.reward_type == RewardType.CARD and self.skipped_cards:
                    continue
                else:
                    return CombatRewardAction(reward_item)
            self.skipped_cards = False
            return ProceedAction()
        elif self.game.screen_type == ScreenType.MAP:
            return self.make_map_choice()
        elif self.game.screen_type == ScreenType.BOSS_REWARD:
            relics = self.game.screen.relics
            best_boss_relic = self.priorities.get_best_boss_relic(relics)
            return BossRewardAction(best_boss_relic)
        elif self.game.screen_type == ScreenType.SHOP_SCREEN:
            if self.game.screen.purge_available and self.game.gold >= self.game.screen.purge_cost:
                return ChooseAction(name="purge")
            for card in self.game.screen.cards:
                if self.game.gold >= card.price and not self.priorities.should_skip(card):
                    return BuyCardAction(card)
            for relic in self.game.screen.relics:
                if self.game.gold >= relic.price:
                    return BuyRelicAction(relic)
            return CancelAction()
        elif self.game.screen_type == ScreenType.GRID:
            if not self.game.choice_available:
                return ProceedAction()
            if self.game.screen.for_upgrade or self.choose_good_card:
                available_cards = self.priorities.get_sorted_cards(self.game.screen.cards)
            else:
                available_cards = self.priorities.get_sorted_cards(self.game.screen.cards, reverse=True)
            num_cards = self.game.screen.num_cards
            return CardSelectAction(available_cards[:num_cards])
        elif self.game.screen_type == ScreenType.HAND_SELECT:
            if not self.game.choice_available:
                return ProceedAction()
            # Usually, we don't want to choose the whole hand for a hand select. 3 seems like a good compromise.
            num_cards = min(self.game.screen.num_cards, 3)
            return CardSelectAction(self.priorities.get_cards_for_action(self.game.current_action, self.game.screen.cards, num_cards))
        else:
            return ProceedAction()

    def choose_rest_option(self):
        rest_options = self.game.screen.rest_options
        if len(rest_options) > 0 and not self.game.screen.has_rested:
            if RestOption.REST in rest_options and self.game.current_hp < self.game.max_hp / 2:
                return RestAction(RestOption.REST)
            elif RestOption.REST in rest_options and self.game.act != 1 and self.game.floor % 17 == 15 and self.game.current_hp < self.game.max_hp * 0.9:
                return RestAction(RestOption.REST)
            elif RestOption.SMITH in rest_options:
                return RestAction(RestOption.SMITH)
            elif RestOption.LIFT in rest_options:
                return RestAction(RestOption.LIFT)
            elif RestOption.DIG in rest_options:
                return RestAction(RestOption.DIG)
            elif RestOption.REST in rest_options and self.game.current_hp < self.game.max_hp:
                return RestAction(RestOption.REST)
            else:
                return ChooseAction(0)
        else:
            return ProceedAction()

    def count_copies_in_deck(self, card):
        count = 0
        for deck_card in self.game.deck:
            if deck_card.card_id == card.card_id:
                count += 1
        return count

    def choose_card_reward(self):
        reward_cards = self.game.screen.cards
        if self.game.screen.can_skip and not self.game.in_combat:
            pickable_cards = [card for card in reward_cards if self.priorities.needs_more_copies(card, self.count_copies_in_deck(card))]
        else:
            pickable_cards = reward_cards
        if len(pickable_cards) > 0:
            potential_pick = self.priorities.get_best_card(pickable_cards)
            return CardRewardAction(potential_pick)
        elif self.game.screen.can_bowl:
            return CardRewardAction(bowl=True)
        else:
            self.skipped_cards = True
            return CancelAction()

    def generate_map_route(self):
        node_rewards = self.priorities.MAP_NODE_PRIORITIES.get(self.game.act)
        best_rewards = {0: {node.x: node_rewards[node.symbol] for node in self.game.map.nodes[0].values()}}
        best_parents = {0: {node.x: 0 for node in self.game.map.nodes[0].values()}}
        min_reward = min(node_rewards.values())
        map_height = max(self.game.map.nodes.keys())
        for y in range(0, map_height):
            best_rewards[y+1] = {node.x: min_reward * 20 for node in self.game.map.nodes[y+1].values()}
            best_parents[y+1] = {node.x: -1 for node in self.game.map.nodes[y+1].values()}
            for x in best_rewards[y]:
                node = self.game.map.get_node(x, y)
                best_node_reward = best_rewards[y][x]
                for child in node.children:
                    test_child_reward = best_node_reward + node_rewards[child.symbol]
                    if test_child_reward > best_rewards[y+1][child.x]:
                        best_rewards[y+1][child.x] = test_child_reward
                        best_parents[y+1][child.x] = node.x
        best_path = [0] * (map_height + 1)
        best_path[map_height] = max(best_rewards[map_height].keys(), key=lambda x: best_rewards[map_height][x])
        for y in range(map_height, 0, -1):
            best_path[y - 1] = best_parents[y][best_path[y]]
        self.map_route = best_path

    def make_map_choice(self):
        if len(self.game.screen.next_nodes) > 0 and self.game.screen.next_nodes[0].y == 0:
            self.generate_map_route()
            self.game.screen.current_node.y = -1
        if self.game.screen.boss_available:
            return ChooseMapBossAction()
        chosen_x = self.map_route[self.game.screen.current_node.y + 1]
        for choice in self.game.screen.next_nodes:
            if choice.x == chosen_x:
                return ChooseMapNodeAction(choice)
        # This should never happen
        return ChooseAction(0)

