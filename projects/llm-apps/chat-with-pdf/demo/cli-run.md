# CLI run (deepseek-flash, hybrid retriever)

Real output, unedited.

```bash
PYTHONPATH=src python -m pdf_chat eval/practice/observatory-handbook.pdf "What do I need to do before I can use the big telescope on my own?" "What happens to my photos on the observatory computer?" "Is there parking at the site?"
```

```
10 chunks, retriever: hybrid

Q: What do I need to do before I can use the big telescope on my own?
A: Book every use of the main 16-inch telescope, Lantern, in the paper logbook in the warm room at least 48 hours ahead [p. 2]. You should also read the handbook once before your first night under the dome [p. 1].

Q: What happens to my photos on the observatory computer?
A: Raw image files on the observatory computer are deleted after 90 days, so you should copy anything you want to keep to your own drive before then [p. 6].

Q: Is there parking at the site?
A: Not in the document.

```
