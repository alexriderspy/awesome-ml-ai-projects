class Note:
    def __init__(self, title, tags=None):
        self.title = title
        self.tags = list(tags or [])

    def tag(self, label):
        if label not in self.tags:
            self.tags.append(label)
        return self
