from typing import Callable


class Comparable(object):
	def __init__(self) -> None:
		super().__init__()

	def __eq__(self, __o: object) -> bool:
		for attribute in dir(self):
			if attribute[:1] != "_":
				data = getattr(self, attribute)
				if not isinstance(data, Callable):
					same_attr = data == getattr(__o, attribute)
					if not same_attr:
						return False
		return True

	def __hash__(self):
		attr_values = []
		for attribute in dir(self):
			if attribute[:1] != "_":
				data = getattr(self, attribute)
				if not isinstance(data, Callable):
					attr_values.append(data)
		return hash(tuple(attr_values))

def largest_contionus(sequence:set, sort_key=None, next_diff=None, pop=True):
	"""Given a sequence {1,2,4,5}, returns the largest contionus number, i.e. 2

	Args:
		sequence ([type]): an set
		sort_key (Callable): given an element of the set, what key should I use to compare
		next_diff (Callable): given an element of the set, what should be DIFFERENCE with the next expected value
		pop (bool, optional): Removes the numbers including and below the largest continous 
		number. Pop=False keeps the larges continous ones. Defaults to True.

	Returns:
		[type]: [description]
	"""
	sequence = list(sequence)
	if len(sequence) == 0:
		return None, set(sequence)
	elif len(sequence) == 1:
		return sequence[0], set(sequence)
	
	# more than 1 elements
	if sort_key is None:
		sequence = sorted(sequence)
	else:
		sequence = sorted(sequence, key=sort_key)
	last_seq = sequence[0]
	
	new_sequence = set()
	if not pop:
		new_sequence.add(last_seq) # add head
	for seq in sequence[1:]:
		# if we have key
		diff = next_diff(last_seq) if next_diff is not None else 1
		if sort_key is not None:
			if sort_key(seq) == sort_key(last_seq) + diff:
				if not pop:
					new_sequence.add(seq)
				last_seq = seq
			else:
				if pop:
					new_sequence.add(seq)
				else:
					break
		else:
			if seq == last_seq + diff:
				if not pop:
					new_sequence.add(seq)
				last_seq = seq
			else:
				if pop:
					new_sequence.add(seq)
				else:
					break
	new_sequence.add(last_seq)
	return last_seq, new_sequence