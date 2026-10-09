import hashlib
import json

import joblib
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import silhouette_score

from src.data import ROOT
from src.language import translate

MODEL = "intfloat/multilingual-e5-small"
REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
STOP = "a o as os de da do das dos e em um uma para por com que nao não eu me se meu minha foi mais muito produto recebi compra bom boa otimo ótimo estou esta está esse essa ele ela no na ao pelo pela ser ter mas ja já ainda so só como tem estava tudo bem tive quando pois mesmo loja".split()


def cluster_complaints(frame):
    sample = frame.loc[frame["review_score"].le(2)].copy()
    sample["text"] = sample["review_comment_title"].fillna("") + ". " + sample["review_comment_message"].fillna("")
    sample["text"] = sample["text"].str.replace(r"\s+", " ", regex=True).str.strip(" .")
    sample = sample.loc[sample["text"].str.len().ge(15)].reset_index(drop=True)
    fingerprint = hashlib.sha256((MODEL + REVISION + "\n".join(sample["text"])).encode()).hexdigest()[:16]
    cache = ROOT / "data" / "processed" / f"embeddings_{fingerprint}.npy"
    if cache.exists():
        embeddings = np.load(cache)
    else:
        encoder = SentenceTransformer(MODEL, revision=REVISION, device="cpu")
        texts = ["query: " + text for text in sample["text"]]
        embeddings = encoder.encode(texts, batch_size=64, show_progress_bar=True, normalize_embeddings=True)
        np.save(cache, embeddings)
    train_mask = (
        sample["order_purchase_timestamp"].lt("2018-04-01")
        & sample["review_answer_timestamp"].lt("2018-04-01")
    ).to_numpy()
    clustering = KMeans(n_clusters=10, n_init=10, random_state=42)
    clustering.fit(embeddings[train_mask])
    sample["cluster"] = clustering.predict(embeddings)
    joblib.dump(clustering, ROOT / "models" / "complaint_clusters.joblib")
    train = sample.loc[train_mask]
    vectorizer = TfidfVectorizer(stop_words=STOP, ngram_range=(1, 2), min_df=5, max_df=0.5, max_features=10000)
    matrix = vectorizer.fit_transform(train["text"])
    vocabulary = vectorizer.get_feature_names_out()
    rows = []
    examples = []
    distance = clustering.transform(embeddings)
    for cluster in range(10):
        mean_tfidf = np.asarray(matrix[train["cluster"].eq(cluster).to_numpy()].mean(axis=0)).ravel()
        words = vocabulary[np.argsort(mean_tfidf)[-8:][::-1]].tolist()
        group = train.loc[train["cluster"].eq(cluster)]
        closest = group.iloc[np.argsort(distance[group.index, cluster])[:5]]
        rows.append({"cluster": cluster, "train_reviews": len(group), "keywords": ", ".join(words)})
        for _, row in closest.iterrows():
            examples.append({"cluster": cluster, "order_id": row["order_id"], "text": row["text"], "score": row["review_score"], "delay_days": row["delay_days"]})
    pd.DataFrame(examples).to_csv(ROOT / "reports" / "topic_examples.csv", index=False)
    pd.DataFrame(rows).to_csv(ROOT / "reports" / "topic_keywords.csv", index=False)
    audit = train.groupby("cluster").sample(n=5, random_state=42)
    audit[["order_id", "cluster", "text"]].sort_values(["cluster", "order_id"]).to_csv(ROOT / "reports" / "topic_audit_sample.csv", index=False)
    metadata = {
        "model": MODEL, "revision": REVISION, "clusters": 10,
        "reviews": len(sample), "train_reviews": int(train_mask.sum()),
        "silhouette": float(silhouette_score(embeddings[train_mask], sample.loc[train_mask, "cluster"], sample_size=1500, random_state=42)),
        "fingerprint": fingerprint,
    }
    (ROOT / "reports" / "topic_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    sample[["order_id", "text", "cluster"]].to_parquet(ROOT / "data" / "processed" / "complaints.parquet", index=False)
    names_path = ROOT / "reports" / "topic_labels.json"
    if names_path.exists():
        names = json.loads(names_path.read_text())
        topics = sample.groupby("cluster").agg(reviews=("order_id", "size"), late_rate=("late", "mean"), average_score=("review_score", "mean")).reset_index()
        topics["label"] = topics["cluster"].map(lambda k: names[str(k)]["label"])
        topics["family"] = topics["cluster"].map(lambda k: names[str(k)]["family"])
        topics["label_it"] = topics["cluster"].map(lambda k: names[str(k)]["label_it"])
        topics["family_it"] = topics["family"].map(lambda family: translate(family, "it"))
        topics.to_csv(ROOT / "reports" / "topics.csv", index=False)
        sample["family"] = sample["cluster"].map(lambda k: names[str(k)]["family"])
        for period, mask in [("all", np.ones(len(sample), dtype=bool)), ("test", sample["order_purchase_timestamp"].ge("2018-04-01") & sample["order_purchase_timestamp"].lt("2018-08-01") & sample["review_answer_timestamp"].lt("2018-09-01") & sample["order_delivered_customer_date"].lt("2018-09-01"))]:
            counts = sample.loc[mask].groupby("family").size().rename("reviews").reset_index()
            counts["share"] = counts["reviews"] / counts["reviews"].sum()
            counts.to_csv(ROOT / "reports" / f"complaint_families_{period}.csv", index=False)
    return sample, metadata
