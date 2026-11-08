from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.preprocessing import StandardScaler


def a(X, y):
    scaler = StandardScaler()
    # ruleid: ml-fit-before-split
    Xs = scaler.fit_transform(X)
    X_tr, X_te, y_tr, y_te = train_test_split(Xs, y)
    return X_tr


def b(X, y, model):
    scaler = StandardScaler()
    # ruleid: ml-fit-before-split
    Xs = scaler.fit_transform(X)
    return cross_val_score(model, Xs, y)


def c(X, y):
    scaler = StandardScaler()
    # ruleid: ml-fit-before-split
    scaler.fit(X)
    return train_test_split(X, y)
