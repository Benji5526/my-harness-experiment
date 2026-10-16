def subtotal(items):
	"""(가격, 수량) 목록의 합계."""
	return sum(p * q for p, q in items)
