// Foundry architecture fitness — Java (ArchUnit).
//
// ArchUnit rules ARE JUnit tests, so this runs under `mise run test` with no verb
// change. Drop it in src/test/java/<base>/arch/ and change the package + base-package
// below. Requires the ArchUnit test dependency:
//   testImplementation("com.tngtech.archunit:archunit-junit5:1.3.0")   // pin the version
//
// ARCHITECTURE-AGNOSTIC. Hexagonal (AutoApplicant's shape) is the default; swap the
// layer/access lines for classic-layered, clean/onion, or modular — see the examples
// at the bottom and designs/arch-fitness.md.
//
// RATCHET: every rule is wrapped in FreezingArchRule.freeze(...). On first run it
// records today's violations into a store (default: archunit_store/, committed) and
// passes; thereafter only NEW violations fail, and the store may only shrink.
// ruleset-guard watches the store files with the `lines` kind.
package com.example.arch; // <- your base package + ".arch"

import com.tngtech.archunit.core.importer.ImportOption;
import com.tngtech.archunit.junit.AnalyzeClasses;
import com.tngtech.archunit.junit.ArchTest;
import com.tngtech.archunit.lang.ArchRule;
import com.tngtech.archunit.library.freeze.FreezingArchRule;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;
import static com.tngtech.archunit.library.Architectures.layeredArchitecture;
import static com.tngtech.archunit.library.dependencies.SlicesRuleDefinition.slices;

@AnalyzeClasses(
    packages = "com.example", // <- your base package
    importOptions = ImportOption.DoNotIncludeTests.class)
class ArchitectureTest {

    // --- Layer boundaries (hexagonal example) -------------------------------
    // `whereLayer(X).mayOnlyBeAccessedByLayers(...)` reads "who may depend on X".
    @ArchTest
    static final ArchRule layerBoundaries = FreezingArchRule.freeze(
        layeredArchitecture().consideringOnlyDependenciesInLayers()
            .layer("Domain").definedBy("..domain..")
            .layer("Port").definedBy("..port..")
            .layer("Usecase").definedBy("..usecase..")
            .layer("Adapter").definedBy("..adapter..")
            .layer("Config").definedBy("..config..")
            // Domain and Port are the core: nothing below them may be reached upward.
            .whereLayer("Adapter").mayNotBeAccessedByAnyLayer()
            .whereLayer("Usecase").mayOnlyBeAccessedByLayers("Adapter", "Config")
            .whereLayer("Port").mayOnlyBeAccessedByLayers("Usecase", "Adapter", "Config")
            .whereLayer("Domain").mayOnlyBeAccessedByLayers("Port", "Usecase", "Adapter", "Config"));

    // --- Framework-freedom: the domain stays plain --------------------------
    @ArchTest
    static final ArchRule domainIsFrameworkFree = FreezingArchRule.freeze(
        noClasses().that().resideInAPackage("..domain..")
            .should().dependOnClassesThat()
            .resideInAnyPackage("org.springframework..", "jakarta..", "..adapter..", "..config.."));

    // --- No package cycles --------------------------------------------------
    @ArchTest
    static final ArchRule noCycles = FreezingArchRule.freeze(
        slices().matching("com.example.(*)..") // <- your base package
            .should().beFreeOfCycles());
}

// ---- example architectures (replace the layerBoundaries rule) --------------
//
// Classic layered (n-tier): controller -> service -> repository
//   layeredArchitecture().consideringOnlyDependenciesInLayers()
//     .layer("Web").definedBy("..controller..", "..web..")
//     .layer("Service").definedBy("..service..")
//     .layer("Data").definedBy("..repository..", "..dao..")
//     .whereLayer("Web").mayNotBeAccessedByAnyLayer()
//     .whereLayer("Service").mayOnlyBeAccessedByLayers("Web")
//     .whereLayer("Data").mayOnlyBeAccessedByLayers("Service");
//
// Clean / onion: entities <- usecases <- interfaces <- frameworks
//   .layer("Entities").definedBy("..entities..") ... .whereLayer("Entities").mayOnlyBeAccessedByLayers("Usecases","Interfaces","Frameworks") ...
//
// Modular / feature isolation: features never depend on each other, only a shared kernel.
//   Use noClasses() per feature instead of layeredArchitecture():
//     noClasses().that().resideInAPackage("..features.billing..")
//       .should().dependOnClassesThat().resideInAPackage("..features.auth..")
//   or slices().matching("..features.(*)..").should().notDependOnEachOther().
