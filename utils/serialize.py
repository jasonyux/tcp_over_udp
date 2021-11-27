import pickle

def serialize(object):
	return pickle.dumps(object)

def deserialize(object):
	return pickle.loads(object)