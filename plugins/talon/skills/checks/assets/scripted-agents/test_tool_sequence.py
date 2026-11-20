"""Exercise the installed Agents SDK with local tool data and scripted model turns."""

from importlib.metadata import version
import unittest

from agents import Agent, RunConfig, Runner
from agents.decorators import tool
from agents.testing import (
    ModelStep,
    ScriptedModel,
    UnconsumedModelSteps,
    UnexpectedModelCall,
    assistant_message,
    function_call,
)


class ToolSequenceTest(unittest.IsolatedAsyncioTestCase):
    async def test_lookup_then_reserve(self):
        calls = []

        @tool
        def find_slot(day: str) -> str:
            """Find the fixture slot for a day."""
            calls.append(("find_slot", day))
            return {"Tuesday": "slot-7"}[day]

        @tool
        def reserve_slot(slot_id: str) -> str:
            """Reserve a slot in the fixture."""
            calls.append(("reserve_slot", slot_id))
            return {"slot-7": "reservation-1"}[slot_id]

        def assert_tool_output(call, call_id, expected):
            outputs = [item["output"] for item in call.input
                       if item.get("type") == "function_call_output" and item.get("call_id") == call_id]
            self.assertEqual(outputs, [expected])

        def request_reservation(call):
            assert_tool_output(call, "call_lookup", "slot-7")
            return [function_call("reserve_slot", {"slot_id": "slot-7"}, call_id="call_reserve")]

        def confirm_reservation(call):
            assert_tool_output(call, "call_reserve", "reservation-1")
            return [assistant_message("Reserved as reservation-1.")]

        model = ScriptedModel([
            [function_call("find_slot", {"day": "Tuesday"}, call_id="call_lookup")],
            ModelStep.respond(request_reservation),
            ModelStep.respond(confirm_reservation),
        ])
        agent = Agent(name="Scheduler", model=model, tools=[find_slot, reserve_slot])
        result = await Runner.run(agent, "Reserve a slot for Tuesday.",
                                  run_config=RunConfig(tracing_disabled=True), max_turns=4)
        self.assertEqual(result.final_output, "Reserved as reservation-1.")
        self.assertEqual(calls, [("find_slot", "Tuesday"), ("reserve_slot", "slot-7")])
        self.assertEqual(len(model.calls), 3)
        model.assert_complete()

    async def test_unscripted_call_fails(self):
        model = ScriptedModel([])
        with self.assertRaises(UnexpectedModelCall):
            await Runner.run(Agent(name="Empty script", model=model), "Reserve a slot.",
                             run_config=RunConfig(tracing_disabled=True))

    async def test_unused_step_fails(self):
        model = ScriptedModel([[assistant_message("Done.")], [assistant_message("Unused.")]])
        await Runner.run(Agent(name="Early finish", model=model), "Reserve a slot.",
                         run_config=RunConfig(tracing_disabled=True))
        with self.assertRaises(UnconsumedModelSteps):
            model.assert_complete()


if __name__ == "__main__":
    print(f"openai-agents {version('openai-agents')}", flush=True)
    unittest.main()
