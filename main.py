import itertools
import datetime
import sys
import os

from spirecomm.communication.coordinator import Coordinator
from spirecomm.ai.agent import SimpleAgent
from spirecomm.spire.character import PlayerClass
import traceback

root_dir = os.path.dirname(os.path.abspath(__file__))
log_error_file = os.path.join(root_dir, "log_error.txt")

if __name__ == "__main__":
    try:
        agent = SimpleAgent()
        coordinator = Coordinator()
        coordinator.signal_ready()
        coordinator.register_command_error_callback(agent.handle_error)
        coordinator.register_state_change_callback(agent.get_next_action_in_game)
        coordinator.register_out_of_game_callback(agent.get_next_action_out_of_game)

        # Rotate in a loop through the classes
        for chosen_class in itertools.cycle(PlayerClass):
            agent.change_class(chosen_class)
            result = coordinator.play_one_game(chosen_class)

    except Exception as e:
        with open(log_error_file, "w", encoding="UTF-8") as f:
            # Log more detailed information with traceback
            f.write(f"Exception occurred: {str(e)}\n")
            f.write(traceback.format_exc())