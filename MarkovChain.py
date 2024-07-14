import matplotlib.pyplot as plt
import numpy as np

# Probabilities that the attacker won, the defender won and that they tied.
# Index by number of dice being rolled - 1: e.g. A[defender_rolls-1][attacker_rolls-1].
P_A = [[15/36, 125/216, 855/1296], [55/216, 295/1296, 2890/7776]];
P_D = [[21/36, 91/216, 441/1296], [161/216, 581/1296, 2275/7776]];
P_T = [[0, 0, 0], [0, 420/1296, 2611/7776]];

def average_remaining_attackers(A, D):

	# Computes the exact average number of remaining attackers
	# from a battle between A attackers and D defenders using
	# a Markov chain. Note that we always leave one attacker behind,
	# so A+1 is the number of units on the attacking territory.
    
    # States are ordered as follows:
    #     {(1, 1), (1, 2), ..., (1, D), (2, 1), (2, 2), ..., (2, D), ..., (A, D), (0, 1), (0, 2), ..., (0, D), (1, 0), (2, 0), ..., (A, 0)}.
    # The first A*D states are transient, while the last A+D states are absorbing.
    states = np.mgrid[1:A+1:1, 1:D+1:1].reshape(2, -1).T;
    states = np.vstack((states, np.c_[np.zeros(D), np.linspace(1, D, D).T]));
    states = np.vstack((states, np.c_[np.linspace(1, A, A).T, np.zeros(A)]));
    
	# Construct matrices Q and R such that the Markov transition matrix is
	#         (Q R)
	#     P = (0 I).
    Q_dim = A*D; R_dim = A+D;
    Q = np.empty([Q_dim, Q_dim]);
    R = np.empty([Q_dim, R_dim]);
    
    for x in range(Q_dim):
        for y in range(Q_dim+R_dim):
            # Determine the probability of going from state x to state y.
            P_xy = 0;
            # We can't transition to a state we're already in (unless we're an absorbing state).
            if x != y:
                state_x = states[x];
                state_y = states[y];
                delta_state = state_x - state_y;
                # Number of dice being rolled - 1.
                attacker_rolls = min(int(state_x[0]), 3);
                defender_rolls = min(int(state_x[1]), 2);
                # Make sure no one is gaining units and we're not losing more than 2 total.
                if delta_state[0] >= 0 and delta_state[1] >= 0 and delta_state[0] + delta_state[1] == min(attacker_rolls, defender_rolls):
                    if delta_state[0] == 0:
                        # The attacker won.
                        P_xy = P_A[defender_rolls-1][attacker_rolls-1];
                    elif delta_state[1] == 0:
                        # The defender won.
                        P_xy = P_D[defender_rolls-1][attacker_rolls-1];
                    else:
                        # They tied.
                        P_xy = P_T[defender_rolls-1][attacker_rolls-1];
                    #
                #
            #
            if y < Q_dim:
                Q[x, y] = P_xy;
            else:
                R[x, y-Q_dim] = P_xy;
            #
        #
    #
    
	# F = (I - Q)^{-1} R = (f_ij)
    F = np.matmul(np.linalg.inv(np.identity(Q_dim) - Q), R);
	# Note that f_{AD, D+k} is the probability that k attackers will remain.
    return np.sum(np.multiply(F[A*D-1, D:], np.linspace(1, A, A)));
    
#


##################################################


dim = 40;
win = np.zeros([dim, dim]); rem = np.zeros([dim, dim]);
for x in range(rem.shape[0]):
    for y in range(rem.shape[1]):
        A = y+1; D = x+1;
        F = average_remaining_attackers(A, D);
        win[x, y] = np.sum(F[A*D-1, D:]);
        rem[x, y] = 1+np.sum(np.multiply(F[A*D-1, D:], np.linspace(1, A, A)));
    #
#
np.savetxt('win_exact_40.txt', win);
np.savetxt('remaining_exact_40.txt', rem);

fig, (ax1, ax2) = plt.subplots(1, 2);
fig.set_size_inches(15, 3);
fig.subplots_adjust(wspace = 0.05);

ax1.set(xlabel = "Defending Armies");
ax1.set(ylabel = "Attacking Armies");
img = ax1.imshow(win.T, extent = [0.5, win.shape[0]+0.5, 0.5, win.shape[1]+0.5], origin = "lower");
plt.colorbar(img, ax=ax1, label = "Average Attacker Win %");

ax2.set(xlabel = "Defending Armies");
ax2.set(ylabel = "Attacking Armies");
img = ax2.imshow(rem.T, extent = [0.5, rem.shape[0]+0.5, 0.5, rem.shape[1]+0.5], origin = "lower");
plt.colorbar(img, ax=ax2, label = "Average Attackers Remaining");