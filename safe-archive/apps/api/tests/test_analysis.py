"""AI requests send only bounded visible text and disable response storage."""

import asyncio
from types import SimpleNamespace

from app.application import analysis


def test_analysis_boundary(monkeypatch) -> None:
    calls = []

    class FakeResponses:
        async def parse(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(output_parsed=analysis.AnalysisResult(
                summary="Review this text", entities=[], detected_threats=[], detected_pii=[], tags=[], timeline=[]
            ))

    class FakeClient:
        def __init__(self, **kwargs):
            self.responses = FakeResponses()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

    monkeypatch.setattr(analysis, "AsyncOpenAI", FakeClient)
    result = asyncio.run(analysis.analyze_visible_text("visible page " * 3000, api_key="test-key", model="test-model"))
    assert result.summary == "Review this text"
    assert calls[0]["store"] is False
    assert len(calls[0]["input"]) < 20100
    assert calls[0]["text_format"] is analysis.AnalysisResult
