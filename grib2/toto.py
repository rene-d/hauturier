#!/usr/bin/env python3


# https://stackoverflow.com/questions/11214118/3d-extrapolation-in-python-basically-scipy-griddata-extended-to-extrapolate


# %%
import numpy as np
import matplotlib.pyplot as plt
import c2d
import scipy.interpolate


# %%


def plot_3d(x, y, z, w=None, show=True):
    fig = plt.figure()
    ax = fig.add_subplot(projection="3d")
    # ax = axes3d.Axes3D(fig)
    ax.scatter(x, y, z, c=w if not w is None else "b")
    plt.show()


# %%
x, y, u, v = c2d.get()

fig = plt.figure()
ax = fig.add_subplot(projection="3d")
ax.scatter(x, y, u, c="b")


# %%

xs = np.arange(x.min(), x.max(), c2d.iDirectionIncrementInDegrees)
ys = np.arange(y.min(), y.max(), c2d.jDirectionIncrementInDegrees)

xnew, ynew = np.meshgrid(xs, ys)
xnew = xnew.flatten()
ynew = ynew.flatten()
# %%
rbf3 = scipy.interpolate.Rbf(x, y, u, function="linear", smooth=0)
znew = rbf3(xnew, ynew)

ax.scatter(xnew, ynew, znew, c="r")
plt.show()