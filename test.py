from Kronos import Kronos

kronos = Kronos(headless=False,dry_run=True,persist=True)
print(kronos.diag())
time.sleep(60)
print(kronos.diag())
time.sleep(10*60)
print(kronos.diag())
time.sleep(30*60)
