import re
import sys
#from utils import write_status
from nltk.stem.porter import PorterStemmer


def preprocess_word(word):
    # Remove punctuation
    word = word.strip('\'"?!,.():;')
    # Convert more than 2 letter repetitions to 2 letter
    # funnnnny --> funny
    word = re.sub(r'(.)\1+', r'\1\1', word)
    # Remove - & '
    word = re.sub(r'(-|\')', '', word)
    return word


def is_valid_word(word):
    # Check if word begins with an alphabet
    return (re.search(r'^[a-zA-Z][a-z0-9A-Z\._]*$', word) is not None)


def handle_emojis(tweet):
    # Smile -- :), : ), :-), (:, ( :, (-:, :')
    tweet = re.sub(r'(:\s?\)|:-\)|\(\s?:|\(-:|:\'\))', ' EMO_POS ', tweet)
    # Laugh -- :D, : D, :-D, xD, x-D, XD, X-D
    tweet = re.sub(r'(:\s?D|:-D|x-?D|X-?D)', ' EMO_POS ', tweet)
    # Love -- <3, :*
    tweet = re.sub(r'(<3|:\*)', ' EMO_POS ', tweet)
    # Wink -- ;-), ;), ;-D, ;D, (;,  (-;
    tweet = re.sub(r'(;-?\)|;-?D|\(-?;)', ' EMO_POS ', tweet)
    # Sad -- :-(, : (, :(, ):, )-:
    tweet = re.sub(r'(:\s?\(|:-\(|\)\s?:|\)-:)', ' EMO_NEG ', tweet)
    # Cry -- :,(, :'(, :"(
    tweet = re.sub(r'(:,\(|:\'\(|:"\()', ' EMO_NEG ', tweet)
    return tweet


def preprocess_tweet(tweet):
    processed_tweet = []
    # Convert to lower case
    tweet = tweet.lower()
    # Replaces URLs with the word URL
    tweet = re.sub(r'((www\.[\S]+)|(https?://[\S]+))', ' URL ', tweet)
    # Replace @handle with the word USER_MENTION
    tweet = re.sub(r'@[\S]+', 'USER_MENTION', tweet)
    # Replaces #hashtag with hashtag
    tweet = re.sub(r'#(\S+)', r' \1 ', tweet)
    # Remove RT (retweet)
    tweet = re.sub(r'\brt\b', '', tweet)
    # Replace 2+ dots with space
    tweet = re.sub(r'\.{2,}', ' ', tweet)
    # Strip space, " and ' from tweet
    tweet = tweet.strip(' "\'')
    # Replace emojis with either EMO_POS or EMO_NEG
    tweet = handle_emojis(tweet)
    # Replace multiple spaces with a single space
    tweet = re.sub(r'\s+', ' ', tweet)
    words = tweet.split()

    for word in words:
        word = preprocess_word(word)
        if is_valid_word(word):
            #if use_stemmer:
            #   word = str(porter_stemmer.stem(word))
            processed_tweet.append(word)

    return ' '.join(processed_tweet)


def preprocess_csv(csv_file_name, processed_file_name, test_file=False):
    save_to_file = open(processed_file_name, 'w')

    with open(csv_file_name, 'r',encoding='ISO-8859-1') as csv:
        lines = csv.readlines()
        total = len(lines)
        for i, line in enumerate(lines):
            tweet_id = line[:line.find(',')]
            if not test_file:
                line = line[1 + line.find(','):]
                positive = int(line[:line.find(',')])
            line = line[1 + line.find(','):]
            tweet = line
            processed_tweet = preprocess_tweet(tweet)
            if not test_file:
                save_to_file.write('%s,%d,%s\n' %
                                   (tweet_id, positive, processed_tweet))
            else:
                save_to_file.write('%s,%s\n' %
                                   (tweet_id, processed_tweet))
            write_status(i + 1, total)
    save_to_file.close()
    print ('\nSaved processed tweets to: %s' % processed_file_name)
    return processed_file_name


# if __name__ == '__main__':
#     if len(sys.argv) != 2:
#         print ('Usage: python preprocess.py <raw-CSV>')
#         exit()
#     use_stemmer = False
#     csv_file_name = sys.argv[1]
#     processed_file_name = sys.argv[1][:-4] + '-processed.csv'
#     if use_stemmer:
#         porter_stemmer = PorterStemmer()
#         processed_file_name = sys.argv[1][:-4] + '-processed-stemmed.csv'
#     preprocess_csv(csv_file_name, processed_file_name, test_file=True)


username = input("Enter username: ")
tweet = input("Enter a tweet: ")
earphones = input("Enter 'Yes' if you are wearing earphones, 'No' otherwise: ")
time = input("Enter the time of the day: Morning/Afternoon/Evening: ")

def top_n_words(pkl_file_name, N, shift=0):
    """
    Returns a dictionary of form {word:rank} of top N words from a pickle
    file which has a nltk FreqDist object generated by stats.py

    Args:
        pkl_file_name (str): Name of pickle file
        N (int): The number of words to get
        shift: amount to shift the rank from 0.
    Returns:
        dict: Of form {word:rank}
    """
    with open(pkl_file_name, 'rb') as pkl_file:
        freq_dist = pickle.load(pkl_file)
    most_common = freq_dist.most_common(N)
    words = {p[0]: i + shift for i, p in enumerate(most_common)}
    return words

import numpy as np
import sys
from keras.models import Sequential, load_model
from keras.layers import Dense, Dropout, Activation
from keras.layers import Embedding
from keras.callbacks import ModelCheckpoint, ReduceLROnPlateau
from keras.layers import LSTM
#import utils
from keras.preprocessing.sequence import pad_sequences
import _pickle as cPickle
from pathlib import Path
# Performs classification using LSTM network.

FREQ_DIST_FILE = 'twtrain-processed-freqdist.pkl'
BI_FREQ_DIST_FILE = 'twtrain-processed-freqdist-bi.pkl'
TRAIN_PROCESSED_FILE = 'twtrain-processed.csv'
TEST_PROCESSED_FILE = 'dataset100_199-processed.csv'
GLOVE_FILE = 'glove-seeds.txt'
dim = 200



def dumpPickle(fileName, content):
    pickleFile = open(fileName, 'wb')
    cPickle.dump(content, pickleFile, -1)
    pickleFile.close()

def loadPickle(fileName):    
    file = open(fileName, 'rb')
    content = cPickle.load(file)
    file.close()
    
    return content
    
def pickleExists(fileName):
    file = Path(fileName)
    
    if file.is_file():
        return True
    
    return False

def get_glove_vectors(vocab):
    print ('Looking for GLOVE vectors')
    glove_vectors = {}
    found = 0
    with open(GLOVE_FILE, 'r',encoding="utf8") as glove_file:
        for i, line in enumerate(glove_file):
            utils.write_status(i + 1, 0)
            tokens = line.split()
            word = tokens[0]
            if vocab.get(word):
                vector = [float(e) for e in tokens[1:]]
                glove_vectors[word] = np.array(vector)
                found += 1
    print ('\n')
    print ('Found %d words in GLOVE' % found)
    return glove_vectors


def get_feature_vector(tweet):
    words = tweet.split()
    feature_vector = []
    for i in range(len(words) - 1):
        word = words[i]
        if vocab.get(word) is not None:
            feature_vector.append(vocab.get(word))
    if len(words) >= 1:
        if vocab.get(words[-1]) is not None:
            feature_vector.append(vocab.get(words[-1]))
    return feature_vector


def process_tweets(csv_file, test_file=True):
    tweets = []
    labels = []
    print ('Generating feature vectors')
    with open(csv_file, 'r') as csv:
        lines = csv.readlines()
        total = len(lines)
        for i, line in enumerate(lines):
            if test_file:
                tweet_id, tweet = line.split(',')
            else:
                tweet_id, sentiment, tweet = line.split(',')
            feature_vector = get_feature_vector(tweet)
            if test_file:
                tweets.append(feature_vector)
            else:
                tweets.append(feature_vector)
                labels.append(int(sentiment))
            utils.write_status(i + 1, total)
    print ('\n')
    return tweets, np.array(labels)


#if __name__ == '__main__':
#     train = len(sys.argv) == 1
#     np.random.seed(1337)
#     vocab_size = 90000
#     batch_size = 500
#     max_length = 40
#     filters = 600
#     kernel_size = 3
#     vocab = utils.top_n_words(FREQ_DIST_FILE, vocab_size, shift=1)
#     #glove_vectors = get_glove_vectors(vocab)
#     glove_vectorsname = 'glove_vectors.pkl'
#     glove_vectors = loadPickle(glove_vectorsname)
#     #tweets, labels = process_tweets(TRAIN_PROCESSED_FILE, test_file=False)
#     tweetsname = 'tweets.pkl'
#     tweets = loadPickle(tweetsname)
#     labelsname = 'labels.pkl'
#     labels = loadPickle(labelsname)
#     embedding_matrix = np.random.randn(vocab_size + 1, dim) * 0.01
#     for word, i in vocab.items():
#         glove_vector = glove_vectors.get(word)
#         if glove_vector is not None:
#             embedding_matrix[i] = glove_vector
#     tweets = pad_sequences(tweets, maxlen=max_length, padding='post')
#     shuffled_indices = np.random.permutation(tweets.shape[0])
#     tweets = tweets[shuffled_indices]
#     labels = labels[shuffled_indices]
#     if train:
#         model = Sequential()
#         model.add(Embedding(vocab_size + 1, dim, weights=[embedding_matrix], input_length=max_length))
#         model.add(Dropout(0.4))
#         model.add(LSTM(128))
#         model.add(Dense(64))
#         model.add(Dropout(0.5))
#         model.add(Activation('relu'))
#         model.add(Dense(1))
#         model.add(Activation('sigmoid'))
#         model.compile(loss='binary_crossentropy', optimizer='adam', metrics=['accuracy'])
#         filepath = "./models/lstm-{epoch:02d}-{loss:0.3f}-{acc:0.3f}-{val_loss:0.3f}-{val_acc:0.3f}.hdf5"
#         checkpoint = ModelCheckpoint(filepath, monitor="loss", verbose=1, save_best_only=True, mode='min')
#         reduce_lr = ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=2, min_lr=0.000001)
#         print (model.summary())
#         model.fit(tweets, labels, batch_size=128, epochs=5, validation_split=0.1, shuffle=True, callbacks=[checkpoint, reduce_lr])
#     else:
#         model = load_model(sys.argv[1])
#         print (model.summary())
#         test_tweets, _ = process_tweets(TEST_PROCESSED_FILE, test_file=True)
#         test_tweets = pad_sequences(test_tweets, maxlen=max_length, padding='post')
#         predictions = model.predict_proba(test_tweets, batch_size=142, verbose=1)
#         print(len(predictions))
#         results = zip(map(str, range(len(test_tweets))), np.round(predictions[:, 0],2).astype(float))
#         utils.save_results_to_csv(results, 'result100_199.csv')

#train = len(sys.argv) == 1
train = 0
np.random.seed(1337)
vocab_size = 90000
batch_size = 500
max_length = 40
filters = 600
kernel_size = 3
vocab = top_n_words(FREQ_DIST_FILE, vocab_size, shift=1)
#glove_vectors = get_glove_vectors(vocab)
glove_vectorsname = 'glove_vectors.pkl'
glove_vectors = loadPickle(glove_vectorsname)
#tweets, labels = process_tweets(TRAIN_PROCESSED_FILE, test_file=False)
tweetsname = 'tweets.pkl'
tweets = loadPickle(tweetsname)
labelsname = 'labels.pkl'
labels = loadPickle(labelsname)
embedding_matrix = np.random.randn(vocab_size + 1, dim) * 0.01
for word, i in vocab.items():
glove_vector = glove_vectors.get(word)
if glove_vector is not None:
    embedding_matrix[i] = glove_vector
tweets = pad_sequences(tweets, maxlen=max_length, padding='post')
shuffled_indices = np.random.permutation(tweets.shape[0])
tweets = tweets[shuffled_indices]
labels = labels[shuffled_indices]
if train:
model = Sequential()
model.add(Embedding(vocab_size + 1, dim, weights=[embedding_matrix], input_length=max_length))
model.add(Dropout(0.4))
model.add(LSTM(128))
model.add(Dense(64))
model.add(Dropout(0.5))
model.add(Activation('relu'))
model.add(Dense(1))
model.add(Activation('sigmoid'))
model.compile(loss='binary_crossentropy', optimizer='adam', metrics=['accuracy'])
filepath = "./models/lstm-{epoch:02d}-{loss:0.3f}-{acc:0.3f}-{val_loss:0.3f}-{val_acc:0.3f}.hdf5"
checkpoint = ModelCheckpoint(filepath, monitor="loss", verbose=1, save_best_only=True, mode='min')
reduce_lr = ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=2, min_lr=0.000001)
print (model.summary())
model.fit(tweets, labels, batch_size=128, epochs=5, validation_split=0.1, shuffle=True, callbacks=[checkpoint, reduce_lr])
else:
#model = load_model(sys.argv[1])
model = load_model("lstm.hdf5")
print (model.summary())
test_tweets, _ = process_tweets(TEST_PROCESSED_FILE, test_file=True)
test_tweets = pad_sequences(test_tweets, maxlen=max_length, padding='post')
predictions = model.predict_proba(test_tweets, batch_size=142, verbose=1)
print(len(predictions))
results = zip(map(str, range(len(test_tweets))), np.round(predictions[:, 0],2).astype(float))
#utils.save_results_to_csv(results, 'result100_199.csv')
