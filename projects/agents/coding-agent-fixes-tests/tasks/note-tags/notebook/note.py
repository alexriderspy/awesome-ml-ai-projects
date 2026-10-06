class Note:
    def __init__(self, title, tags=[]):
        self.title = title
        self.tags = tags

    def tag(self, label):
        if label not in self.tags:
            self.tags.append(label)
        return self
