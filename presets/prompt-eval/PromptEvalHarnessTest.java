// Foundry prompt / agent-output regression harness — Java (JUnit 5).
//
// Generalises AutoApplicant's PromptEvalHarnessTest. Deterministic + OFFLINE: score
// hand-written good/weak samples with YOUR scorer and assert it RANKS them (good >= FLOOR,
// weak <= CEILING, gap >= SEPARATION). Runs under `mise run test` — it IS a test, no new verb.
// foundry ships NO scorer: implement QualityScorer (and, if you assert prompt blocks, a
// prompt composer) in your own code. Fixtures live in src/test/resources/prompt-eval/,
// listed in manifest.json.
//
// RATCHET: the fixture COUNT may only grow (never delete a regression case) — ruleset-guard
// watches manifest.json with the `coverage` kind. Do NOT ratchet the SCORES upward (it
// overfits the scorer). Thresholds are ruleset, guard-watched via the ruleset-file watch.
package com.example.prompteval; // <- your package

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.DynamicTest;
import org.junit.jupiter.api.TestFactory;

import java.io.IOException;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.List;
import java.util.stream.Stream;

import static org.assertj.core.api.Assertions.assertThat;

class PromptEvalHarnessTest {

    private static final int FLOOR = 80;       // a good sample must clear this
    private static final int CEILING = 60;     // a weak sample must stay under this
    private static final int SEPARATION = 30;  // the gap that makes the score trustworthy

    private final ObjectMapper mapper = new ObjectMapper();

    /** YOUR deterministic scorer — this is the domain-specific half foundry does not ship. */
    private int scoreOutput(String output, String input) {
        // return new DocumentQualityEvaluator(...).evaluate(output, input).total();
        throw new UnsupportedOperationException("wire in your QualityScorer");
    }

    private record Fixture(String name, String input, String good, String weak) {}

    private List<Fixture> load() throws IOException {
        List<Fixture> out = new ArrayList<>();
        try (InputStream mf = getClass().getResourceAsStream("/prompt-eval/manifest.json")) {
            assertThat(mf).as("prompt-eval/manifest.json on the test classpath").isNotNull();
            for (JsonNode name : mapper.readTree(mf).path("fixtures")) {
                try (InputStream in = getClass().getResourceAsStream("/prompt-eval/" + name.asText())) {
                    JsonNode n = mapper.readTree(in);
                    out.add(new Fixture(n.path("name").asText(), n.path("input").asText(),
                            n.path("good").asText(), n.path("weak").asText()));
                }
            }
        }
        return out;
    }

    @TestFactory
    Stream<DynamicTest> scorerSeparatesGoodFromWeak() throws IOException {
        return load().stream().map(f -> DynamicTest.dynamicTest(f.name(), () -> {
            int good = scoreOutput(f.good(), f.input());
            int weak = scoreOutput(f.weak(), f.input());
            assertThat(good).as("good sample for %s", f.name()).isGreaterThanOrEqualTo(FLOOR);
            assertThat(weak).as("weak sample for %s", f.name()).isLessThanOrEqualTo(CEILING);
            assertThat(good - weak).as("separation for %s", f.name()).isGreaterThanOrEqualTo(SEPARATION);
        }));
    }
}
