"""CLI demo: python cli.py --prompt '...'"""
import argparse, json
from src.engine import RetailCopilot

p=argparse.ArgumentParser(description="Punjab Sports Mart AI Retail Operations Copilot")
p.add_argument("--prompt", help="Retail operations issue; omit to start a small interactive loop")
p.add_argument("--persona", default="Store Associate")
p.add_argument("--pretty", action="store_true", help="Print the full structured response as JSON")
a=p.parse_args()
engine=RetailCopilot()
if a.prompt:
    result=engine.answer(a.prompt,a.persona)
    if a.pretty: print(json.dumps(result,ensure_ascii=False,indent=2,default=str))
    else:
        print(f"Category: {result['category']} | Priority: {result['priority']} | Confidence: {result['confidence']:.2f}")
        print(f"Escalation: {result['escalation']['required']} → {result['escalation']['team']}")
        print("\n"+result['answer'])
        print("\nCitations:")
        for citation in result['citations']: print(" - "+citation)
        if result['data_used']: print("\nData used: "+", ".join(result['data_used']))
else:
    print("Punjab Sports Mart Copilot — type 'exit' to stop")
    while True:
        prompt=input("\nIssue> ").strip()
        if prompt.lower() in {"exit","quit"}: break
        if not prompt: continue
        result=engine.answer(prompt,a.persona)
        print(f"\n[{result['category']} · {result['priority']} · confidence {result['confidence']:.2f}]")
        print(result['answer'])
        print("Citations: "+"; ".join(result['citations']))
