# Importe general libraries
import sys
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import numpy as np
import pandas as pd
# Import blitz (BNN) modules
from blitz.modules import BayesianLinear
from blitz.utils import variational_estimator
# Import sklearn dataset parsers and samples
from sklearn.datasets import load_boston
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
# Helper lirbaries (viz)
import matplotlib.pyplot as plt
import matplotlib
from tools.console import Console


def load_dataset (filename, summary=False, latent_name_prefix= 'latent_'):
    Console.info("load_dataset called for: ", filename)
    df = pd.read_csv(filename, index_col=0) # use 1t column as ID, the 2nd (relative_path) can be used as part of UUID
    # The number of 'features' are defined by those columns labeled as 'h'xxx, where xx is 0-based index for the h-latent space vector
    # Example: (8 dimensions: h0, h1, ... , h7)
    # relative_path northing [m] easting [m] ... latitude [deg] longitude [deg] recon_loss h0 h1 h2 h3 h4 h5 h6 h7

    # 1) Let's determine number of latent-space dimensions
    df_latent = df.filter(regex=latent_name_prefix)
    n_latents = len(df_latent.columns)
    Console.info ("Latent dimensions: "n_latents)
    # 2) Dtaa alidation, remove invalid entries (e.g. NaN)

    return 1, n_latents
    # return dataset, num_latents
    # read dataset as pandas dataframe



@variational_estimator
class BayesianRegressor(nn.Module):
    def __init__(self, input_dim, output_dim):
        super().__init__()
        # simple 2-layer fully connected linear regressor
        #self.linear = nn.Linear(input_dim, output_dim)
        self.blinear1 = BayesianLinear(input_dim, 128)
        self.sigmoid1 = nn.Sigmoid()
        self.blinear2 = BayesianLinear(128, output_dim)
        
    def forward(self, x):
        x_ = self.blinear1(x)
        x_ = self.sigmoid1(x_)
        return self.blinear2(x_)


def evaluate_regression(regressor,
                        X,
                        y,
                        samples = 100,
                        std_multiplier = 2):
    preds = [regressor(X) for i in range(samples)]
    preds = torch.stack(preds)
    means = preds.mean(axis=0)
    stds = preds.std(axis=0)
    ci_upper = means + (std_multiplier * stds)
    ci_lower = means - (std_multiplier * stds)
    ic_acc = (ci_lower <= y) * (ci_upper >= y)
    ic_acc = ic_acc.float().mean()
    return ic_acc, (ci_upper >= y).float().mean(), (ci_lower <= y).float().mean()



def main(args=None):
    # // TODO : add arg parser, admit input file (dataset), config file, validation dataset file, mode (train, validate, predict)
    Console.info("Geotech landability/measurability predictor from low-res acoustics. Uses Bayesian Neural Networks as predictive engine")
    dataset_filename = "data/koyo-20181121-model-21-output.xls"
    Console.info("Loading dataset: " + dataset_filename)

    Xd, yd = load_dataset(dataset_filename)

    sys.exit(0)

    X, y = load_boston(return_X_y=True)

    print ("X.len:", X.shape)
    print ("y.len:", y.shape)

    X = StandardScaler().fit_transform(X)
    y = StandardScaler().fit_transform(np.expand_dims(y, -1))

    X_train, X_test, y_train, y_test = train_test_split(X,
                                                        y,
                                                        test_size=.25,
                                                        random_state=42)


    X_train, y_train = torch.tensor(X_train).float(), torch.tensor(y_train).float()
    X_test, y_test = torch.tensor(X_test).float(), torch.tensor(y_test).float()
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    regressor = BayesianRegressor(13, 1).to(device)
    optimizer = optim.Adam(regressor.parameters(), lr=0.01)
    criterion = torch.nn.MSELoss()

    ds_train = torch.utils.data.TensorDataset(X_train, y_train)
    dataloader_train = torch.utils.data.DataLoader(ds_train, batch_size=16, shuffle=True)

    ds_test = torch.utils.data.TensorDataset(X_test, y_test)
    dataloader_test = torch.utils.data.DataLoader(ds_test, batch_size=16, shuffle=True)


    iteration = 0
    for epoch in range(100):
        for i, (datapoints, labels) in enumerate(dataloader_train):
            optimizer.zero_grad()
            
            loss = regressor.sample_elbo(inputs=datapoints.to(device),
                            labels=labels.to(device),
                            criterion=criterion,
                            sample_nbr=3,
                            complexity_cost_weight=1/X_train.shape[0])
            loss.backward()
            optimizer.step()
            
            iteration += 1
            if iteration%100==0:
                ic_acc, under_ci_upper, over_ci_lower = evaluate_regression(regressor,
                                                                            X_test.to(device),
                                                                            y_test.to(device),
                                                                            samples=25,
                                                                            std_multiplier=3)
                
                print("CI acc: {:.2f}, CI upper acc: {:.2f}, CI lower acc: {:.2f}".format(ic_acc, under_ci_upper, over_ci_lower))
                print("Loss: {:.4f}".format(loss))


if __name__ == '__main__':
    main()
