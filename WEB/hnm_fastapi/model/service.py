import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib import pyplot as plt
import networkx as nx
from gensim.models import Word2Vec
from sklearn.metrics.pairwise import cosine_similarity
import matplotlib.image as mpimg
import random
from sqlalchemy import create_engine
import mysql.connector


def service_model(articles,transactions,inputdata):
    #  아이템 사용자별 id의 유니크한 갯수를 변수에 담음
    item_freq = transactions.groupby('article_id')['username'].nunique()
    user_freq = transactions.groupby('username')['article_id'].nunique()

    items = item_freq.index
    users = user_freq.index

    filtered_df = transactions[transactions['article_id'].isin(items) & transactions['username'].isin(users)]

    freq = filtered_df.groupby(['username', 'article_id']).size().reset_index(name='frequency')

    GraphTravel_HM = filtered_df.merge(freq, on=['username', 'article_id'], how='left')

    GraphTravel_HM = GraphTravel_HM[GraphTravel_HM['frequency'] >= 1]

    unique_usernames = GraphTravel_HM['username'].unique()

    username_mapping = {id: i for i, id in enumerate(unique_usernames)}

    GraphTravel_HM['username'] = GraphTravel_HM['username'].map(username_mapping)

    item_name_mapping = dict(zip(articles['article_id'], articles['prod_name']))

    G = nx.Graph()

    for index, row in GraphTravel_HM.iterrows():
        G.add_node(row['username'], type='user')
        G.add_node(row['article_id'], type='item')
        G.add_edge(row['username'], row['article_id'], weight=row['frequency'])

    def biased_random_walk(G, start_node, walk_length, p=1, q=1):
        walk = [start_node]

        while len(walk) < walk_length:
            cur_node = walk[-1]
            cur_neighbors = list(G.neighbors(cur_node))

            if len(cur_neighbors) > 0:
                if len(walk) == 1:
                    walk.append(random.choice(cur_neighbors))
                else:
                    prev_node = walk[-2]

                    probability = []
                    for neighbor in cur_neighbors:
                        if neighbor == prev_node:
                            # Return parameter 
                            probability.append(1/p)
                        elif G.has_edge(neighbor, prev_node):
                            # Stay parameter 
                            probability.append(1)
                        else:
                            # In-out parameter 
                            probability.append(1/q)

                    probability = np.array(probability)
                    probability = probability / probability.sum()  # normalize

                    next_node = np.random.choice(cur_neighbors, p=probability)
                    walk.append(next_node)
            else:
                break

        return walk
    def generate_walks(G, num_walks, walk_length, p=1, q=1):
        walks = []
        nodes = list(G.nodes())
        for _ in range(num_walks):
            random.shuffle(nodes)
            for node in nodes:
                walk_from_node = biased_random_walk(G, node, walk_length, p, q)
                walks.append(walk_from_node)
        return walks
    
    # Random Walk 
    walks = generate_walks(G, num_walks=10, walk_length=20, p=9, q=1)
    filtered_walks = [walk for walk in walks if len(walk) >= 5]

    # to String  (for Word2Vec input)
    walks = [[str(node) for node in walk] for walk in walks]
    # Word2Vec train
    model = Word2Vec(walks, vector_size=128, window=5, min_count=0,  hs=1, sg=1, workers=4, epochs=10)

    # node embedding extract
    embeddings = {node_id: model.wv[node_id] for node_id in model.wv.index_to_key}

    def get_user_embedding(username, embeddings):
        return embeddings[str(username)]
    
    def get_rated_items(username, df):
        return set(df[df['username'] == username]['article_id'])

    def calculate_similarities(username, df, embeddings):
        rated_items = get_rated_items(username, df)
        user_embedding = get_user_embedding(username, embeddings)
    
        item_similarities = []
        for item_id in set(df['article_id']):
            if item_id not in rated_items:  
                item_embedding = embeddings[str(item_id)]
                similarity = cosine_similarity([user_embedding], [item_embedding])[0][0]
                item_similarities.append((item_id, similarity))
    
        return item_similarities
    
    def show_images(items, item_name_mapping, num_items, show_similarity=False):
        f, ax = plt.subplots(1, num_items, figsize=(20,10))
        if num_items == 1:
            ax = [ax]
        for i, item in enumerate(items):
            item_id, similarity = item
            print(f"- Item {item_id}: {item_name_mapping[item_id]}", end='')
            if show_similarity:
                print(f" with similarity score: {similarity}")
            else:
                print()
            img_path = f"/Users/jimincheol/Documents/Project/HnM_Project_data/images/0{str(item_id)[:2]}/0{int(item_id)}.jpg"
            try:
                img = mpimg.imread(img_path)
                ax[i].imshow(img)
                ax[i].set_title(f'Item {item_id}')
                ax[i].set_xticks([], [])
                ax[i].set_yticks([], [])
                ax[i].grid(False)
            except FileNotFoundError:
                print(f"Image for item {item_id} not found.")
        plt.show()
        
    
    def recommend_items(user_id, df, embeddings, item_name_mapping, num_items=5):
        item_similarities = calculate_similarities(user_id, df, embeddings)

        recommended_items = sorted(item_similarities, key=lambda x: x[1], reverse=True)[:num_items]

        print(f"\nRecommended items for user {user_id}:")
        show_images(recommended_items, item_name_mapping, num_items, show_similarity=True)


        
    recommend_items = recommend_items(username_mapping[inputdata], GraphTravel_HM, embeddings, item_name_mapping , num_items=5)

    
    return recommend_items
