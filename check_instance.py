import sys

# Add root to path
sys.path.append('/opt/data/home/.zeroshot/worktrees/blazing-storm-57')

from src.ranking import Judgment as DataclassJudgment
from src.svg_judge import Judgment as PydanticJudgment

def test():
    p = PydanticJudgment(
        svg_id="1",
        svg_model_name="m",
        judged_by="j",
        scores={"creativity": 5},
        judge_prompt="PROMPT"
    )
    print(f"Pydantic model: {type(p)}")
    print(f"Is instance of DataclassJudgment? {isinstance(p, DataclassJudgment)}")

if __name__ == "__main__":
    test()
