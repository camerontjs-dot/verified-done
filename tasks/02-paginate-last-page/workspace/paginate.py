def paginate(items, per_page):
    pages = []
    n = len(items) // per_page
    for i in range(n):
        pages.append(items[i * per_page:(i + 1) * per_page])
    return pages
