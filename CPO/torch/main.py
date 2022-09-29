from logger import Logger
from agent import Agent
from graph import Graph
from env import Env

from sklearn.utils import shuffle
from collections import deque
from scipy.stats import norm
from copy import deepcopy
import numpy as np
# import safety_gym
import argparse
import pickle
import random
import torch
import wandb
import copy
import time
import gym
import sys

sys.path.append("/home/ineogi2/RL-Lab/metadrive")
from metadrive import SafeMetaDriveEnv

sys.path.append("/home/ineogi2/RL-Lab")
from PID.PID_controller_v4 import PID_controller

def train(main_args):
    algo_idx = 2
    agent_name = '0929-action-pretrain'
    env_name = "Safe-metadrive-env"
    max_ep_len = 500
    max_steps = 1000
    epochs = 2500
    save_freq = 10
    algo = '{}_{}'.format(agent_name, algo_idx)
    save_name = '_'.join(env_name.split('-')[:-1])
    save_name = "result/{}_{}".format(save_name, algo)
    args = {
        'agent_name':agent_name,
        'save_name': save_name,
        'discount_factor':0.99,
        'hidden1':512,
        'hidden2':512,
        'v_lr':2e-4,
        'cost_v_lr':2e-4,
        'value_epochs':200,
        'batch_size':10000,
        'num_conjugate':10,
        'max_decay_num':10,
        'line_decay':0.8,
        'max_kl':0.01,
        'damping_coeff':0.01,
        'gae_coeff':0.97,
        'cost_d':1.0/1000.0,
    }
    if torch.cuda.is_available():
        device = torch.device('cuda:0')
        print('[torch] cuda is used.')
    else:
        device = torch.device('cpu')
        print('[torch] cpu is used.')

    # for random seed
    seed = algo_idx + random.randint(0, 100)
    np.random.seed(seed)
    random.seed(seed)

    # env = Env(env_name, seed, max_ep_len)
    env=SafeMetaDriveEnv(dict(use_render=True,
                    random_lane_width=True,
                    random_lane_num=True,
                    start_seed=random.randint(0, 1000)))
    agent = Agent(env, device, args)

    # for wandb
    # wandb.init(project='[torch] CPO', entity='ineogi2', name='0927-after-traning-2')
    if main_args.graph: graph = Graph(10, "TRPO", ['score', 'cv', 'policy objective', 'value loss', 'kl divergence', 'entropy'])

    for epoch in range(epochs):
        trajectories = []
        ep_step = 0
        scores = []
        cvs = []
        while ep_step < max_steps:
            state = env.reset()
            # _, _, done, info = env.step([0,0])
            # controller = PID_controller(info)
            # action = [0,0]
            # time_step=0
            score = 0
            cv = 0
            step = 0

            while True:
                # time_step += 1
                # ep_step += 1
                # step += 1
                # print(f'waypoint : {controller.waypoint} / is arrived : {controller.is_arrived} / action : {action[0]}')

                # if controller.is_arrived or time_step > 10:
                #     state_tensor = torch.tensor(state, device=device, dtype=torch.float)
                #     action_tensor = agent.getAction(state_tensor, is_train=True)
                #     waypoint = action_tensor.detach().cpu().numpy()
                    # while waypoint[0]<=0:
                    #     state_tensor = torch.tensor(state, device=device, dtype=torch.float)
                    #     action_tensor = agent.getAction(state_tensor, is_train=True)
                    #     waypoint = action_tensor.detach().cpu().numpy()
                    # controller.update(info, waypoint=waypoint); time_step=0
                ep_step += 1
                step += 1
                state_tensor = torch.tensor(state, device=device, dtype=torch.float)
                action_tensor, clipped_action_tensor = agent.getAction(state_tensor, is_train=True)
                action = action_tensor.detach().cpu().numpy()
                clipped_action = clipped_action_tensor.detach().cpu().numpy()
                next_state, reward, done, info = env.step(clipped_action)

                # action = controller.lane_keeping()
                # next_state, reward, done, info = env.step(action)

                # controller.update(info, waypoint=0)
                cost = info['cost']

                done = True if step >= max_ep_len else done
                fail = True if step < max_ep_len and done else False
                trajectories.append([state, action, reward, cost, done, fail, next_state])

                state = next_state
                score += reward
                cv += info['num_cv']

                if done or step >= max_ep_len:
                    break

            scores.append(score)
            cvs.append(cv)

        v_loss, cost_v_loss, objective, cost_surrogate, kl, entropy = agent.train(trajs=trajectories)
        score = np.mean(scores)
        cvs = np.mean(cvs)
        log_data = {"score":score, 'cv':cv, "value loss":v_loss, "cost value loss":cost_v_loss, "objective":objective, "cost surrogate":cost_surrogate, "kl":kl, "entropy":entropy}
        print(log_data)
        if main_args.graph: graph.update([score, objective, v_loss, kl, entropy])
        # wandb.log(log_data)
        if (epoch + 1)%save_freq == 0:
            agent.save()

    if main_args.graph: graph.update(None, finished=True)


def test(args):
    pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='CPO')
    parser.add_argument('--test', action='store_true', help='For test.')
    parser.add_argument('--resume', type=int, default=0, help='type # of checkpoint.')
    parser.add_argument('--graph', action='store_true', help='For graph.')
    args = parser.parse_args()
    dict_args = vars(args)
    if args.test:
        test(args)
    else:
        train(args)
