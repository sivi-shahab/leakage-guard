from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def split_first(X, y):
    X_tr, X_te, y_tr, y_te = train_test_split(X, y)
    scaler = StandardScaler()
    # ok: ml-fit-before-split
    X_tr_s = scaler.fit_transform(X_tr)
    return X_tr_s, scaler.transform(X_te)


def pipeline_cv(X, y, model):
    # ok: ml-fit-before-split
    return cross_val_score(make_pipeline(StandardScaler(), model), X, y)


def fit_on_train_only(X_train, X_test):
    scaler = StandardScaler()
    # ok: ml-fit-before-split
    scaler.fit(X_train)
    return scaler.transform(X_test)
