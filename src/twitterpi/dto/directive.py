from dataclasses import dataclass

@dataclass
class Directive:
    retweet: bool = False
    favorite: bool = False
    follow: bool = False
    tag: bool = False
    comment: bool = False
