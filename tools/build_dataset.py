"""Author the synthetic dataset. No source exam text or old model responses are used.

    python -m tools.build_dataset
"""
import json
from pathlib import Path
from blindspot.maths import parse, representation

ROOT = Path(__file__).resolve().parents[1]


def problem(pid, title, topic, question, assumptions, symbols, witnesses, steps):
    p = dict(id=pid, title=title, topic=topic, question=question, assumptions=assumptions,
             symbols=symbols, witnesses=witnesses, steps=[])
    for index, (label, text, lhs, expression, operation) in enumerate(steps, 1):
        p["steps"].append(dict(index=index, label=label, text=text, lhs=lhs,
                               operation=operation, **representation(parse(expression, p))))
    return p


def dataset():
    pos, real = {"positive": True}, {"real": True}
    result = {"version": "1.0.0", "origin": "Eight original synthetic problems, authored for Blindspot. Old exam archetypes were inspiration only.",
            "problems": [
        problem("gaussian", "Localising a quantum particle", "Quantum mechanics",
                "On the real line, a particle has wavefunction ψ(x) = A exp(−βx²), with β > 0 and real A > 0. Find A, ⟨x⟩, ⟨x²⟩ and the position uncertainty σₓ.",
                "x ∈ ℝ; β > 0; A is chosen positive. All integrals are over the real line.",
                {"x": real, "beta": pos}, [{"x": "1/3", "beta": "2"}, {"x": "-2/5", "beta": "3"}], [
            ("Normalisation integral", "Evaluate the integral of the unnormalised probability density.", "∫ exp(−2βx²) dx", "sqrt(pi/(2*beta))", "integration"),
            ("Normalisation constant", "Impose unit total probability and choose the positive root.", "A", "(2*beta/pi)**(1/4)", "algebra"),
            ("Mean position", "Integrate x times the normalised density; the integrand is odd.", "⟨x⟩", "0", "integration"),
            ("Second moment", "Integrate x² times the normalised probability density.", "⟨x²⟩", "1/(4*beta)", "integration"),
            ("Position uncertainty", "Take the square root of the variance ⟨x²⟩ − ⟨x⟩².", "σₓ", "1/(2*sqrt(beta))", "algebra")]),
        problem("nonlinear-ode", "A nonlinear initial-value problem", "Mathematical physics",
                "Solve dy/dx = (3x² + 2x)y² with y(0) = 1, on −1/4 < x < 1/4. Use separation of variables and give the branch satisfying the initial condition.",
                "−1/4 < x < 1/4; the selected solution is positive and finite. C is a real integration constant.",
                {"x": real, "y": pos, "C": real}, [{"x": "1/10", "y": "2", "C": "2"}, {"x": "-1/5", "y": "3", "C": "3"}], [
            ("Separate variables", "Divide the differential equation by y² on the positive branch.", "y⁻² dy/dx", "3*x**2+2*x", "algebra"),
            ("Integrate the left side", "Find an antiderivative with respect to y, with its constant absorbed into C.", "∫ y⁻² dy", "-1/y", "integration"),
            ("Integrate the right side", "Integrate the polynomial in x and introduce the integration constant.", "−1/y", "x**3+x**2+C", "integration"),
            ("Apply the initial value", "Substitute x = 0 and y = 1 to fix the constant.", "C", "-1", "algebra"),
            ("Isolate the solution", "Solve for y on the specified interval.", "y(x)", "1/(1-x**2-x**3)", "algebra")]),
        problem("euler-cauchy", "Two power-law modes", "Mathematical physics",
                "Solve x²y″ − 2xy′ − 4y = 0 for x > 0, with y(1) = 3 and y′(1) = 2. Use a power-law trial solution.",
                "x > 0; r, C₁ and C₂ are real. The trial function is xʳ.",
                {"x": pos, "r": real, "C1": real, "C2": real}, [{"x": "2", "r": "2", "C1": "3", "C2": "2"}, {"x": "3", "r": "3", "C1": "2", "C2": "5"}], [
            ("Substitute a power law", "Insert y = xʳ into the differential operator and divide by xʳ.", "residual / xʳ", "r**2-3*r-4", "differentiation"),
            ("Factor the indicial polynomial", "Write the indicial polynomial in factored form; its roots determine the two modes.", "r² − 3r − 4", "(r-4)*(r+1)", "algebra"),
            ("Combine the modes", "Use the two distinct roots to form the general solution.", "y(x)", "C1*x**4+C2/x", "algebra"),
            ("Determine the growing mode", "Solve C₁ + C₂ = 3 and 4C₁ − C₂ = 2 for C₁.", "C₁", "1", "algebra"),
            ("Apply both conditions", "Substitute both constants into the general solution.", "y(x)", "x**4+2/x", "algebra")]),
        problem("viscoelastic", "Driving a viscoelastic solid", "Condensed matter",
                "A Kelvin–Voigt solid obeys η de/dt + G e = σ₀ cos(ωt), with G, η, σ₀, ω > 0. After transients have decayed, set e(t) = A cos(ωt) + B sin(ωt). Determine A, B and the steady periodic strain.",
                "G, η, σ₀ and ω are positive; t, A and B are real. Transients are excluded.",
                {"G": pos, "eta": pos, "sigma0": pos, "omega": pos, "t": real, "A": real, "B": real},
                [{"G": "2", "eta": "3", "sigma0": "5", "omega": "2", "t": "0", "A": "2", "B": "3"},
                 {"G": "3", "eta": "2", "sigma0": "7", "omega": "1", "t": "1", "A": "3", "B": "2"}], [
            ("Cosine balance", "Substitute the strain ansatz and collect the cosine coefficient on the left of the constitutive equation.", "cosine coefficient", "G*A+eta*omega*B", "differentiation"),
            ("Sine balance", "Collect the sine coefficient on the left of the constitutive equation.", "sine coefficient", "G*B-eta*omega*A", "differentiation"),
            ("In-phase amplitude", "Match cosine and sine coefficients to σ₀ and zero, then solve for A.", "A", "G*sigma0/(G**2+eta**2*omega**2)", "algebra"),
            ("Quadrature amplitude", "Solve the same two balance equations for B.", "B", "eta*omega*sigma0/(G**2+eta**2*omega**2)", "algebra"),
            ("Periodic strain", "Insert both amplitudes into the strain ansatz.", "e(t)", "sigma0*(G*cos(omega*t)+eta*omega*sin(omega*t))/(G**2+eta**2*omega**2)", "algebra")]),
        problem("radial-mode", "Where is the particle most likely?", "Quantum mechanics",
                "A spherically symmetric bound-state radial function is R(r) = N r² exp(−r/(3a)), for r ≥ 0 and a > 0. The angular part has unit norm. Find the most probable radius for a radial measurement. You need not determine N.",
                "a > 0 and N > 0. The radial density is P(r) = r²|R(r)|². Use r > 0 when differentiating log P.",
                {"r": pos, "a": pos}, [{"r": "2", "a": "1"}, {"r": "3", "a": "2"}], [
            ("Include the volume factor", "Define q(r) = P(r)/N² and include the radial volume factor.", "q(r)", "r**6*exp(-2*r/(3*a))", "algebra"),
            ("Differentiate the log density", "For positive r, use the logarithmic derivative to locate a stationary point.", "d(log q)/dr", "6/r-2/(3*a)", "differentiation"),
            ("Locate the stationary point", "Set the logarithmic derivative to zero and solve for r.", "r*", "9*a", "algebra"),
            ("Check the maximum", "Evaluate the second log derivative at the stationary point. Since q tends to zero at both endpoints and has one positive stationary point, it is the global maximum.", "d²(log q)/dr² at r*", "-2/(27*a**2)", "differentiation")]),
        problem("angular-momentum", "A cubic angular-momentum state", "Quantum mechanics",
                "Let ψ(x,y) = (x − iy)³. Apply L_z = −iℏ(x ∂/∂y − y ∂/∂x) and determine whether ψ is an eigenfunction, and if so its eigenvalue. Normalisation is not required.",
                "x and y are real Cartesian coordinates; ℏ > 0. The polynomial is an operator test function, not a normalisable state on all space.",
                {"x": real, "y": real, "hbar": pos}, [{"x": "2", "y": "1", "hbar": "1"}, {"x": "1", "y": "3", "hbar": "2"}], [
            ("Differentiate in x", "Differentiate the cubic test function with respect to x.", "∂ψ/∂x", "3*(x-I*y)**2", "differentiation"),
            ("Differentiate in y", "Differentiate the same test function with respect to y.", "∂ψ/∂y", "-3*I*(x-I*y)**2", "differentiation"),
            ("Form the orbital derivative", "Combine the two partial derivatives in the order specified by L_z.", "x ∂ψ/∂y − y ∂ψ/∂x", "-3*I*(x-I*y)**3", "algebra"),
            ("Apply the operator prefactor", "Multiply the orbital derivative by −iℏ.", "L_z ψ", "-3*hbar*(x-I*y)**3", "algebra"),
            ("Read the eigenvalue", "Identify the constant multiplying the original polynomial.", "λ", "-3*hbar", "algebra")]),
        problem("well-energy", "Energy of a shaped well state", "Quantum mechanics",
                "In an infinite well 0 < x < L, a particle of mass m has ψ(x) = N sin³(πx/L), with N > 0. Normalise the state, expand it using φₙ = √(2/L) sin(nπx/L), and calculate ⟨E⟩. You may use sin³θ = (3 sin θ − sin 3θ)/4 and Eₙ = n²π²ℏ²/(2mL²).", 
                "L, m and ℏ are positive. The wavefunction vanishes outside the well. φₙ are orthonormal.",
                {"L": pos, "m": pos, "hbar": pos}, [{"L": "2", "m": "3", "hbar": "1"}, {"L": "3", "m": "2", "hbar": "2"}], [
            ("Integrate the density", "Integrate the square of the unnormalised state from 0 to L.", "∫₀ᴸ sin⁶(πx/L) dx", "5*L/16", "integration"),
            ("Normalise the wavefunction", "Choose the positive normalisation constant.", "N", "4/sqrt(5*L)", "algebra"),
            ("Project onto the first mode", "Use the given trigonometric identity and the normalised eigenfunctions to extract c₁.", "c₁", "3/sqrt(10)", "algebra"),
            ("Project onto the third mode", "Extract c₃ from the same expansion; all other coefficients vanish.", "c₃", "-1/sqrt(10)", "algebra"),
            ("Take the energy expectation", "Weight the first and third energy levels by their squared expansion amplitudes.", "⟨E⟩", "9*pi**2*hbar**2/(10*m*L**2)", "algebra")]),
        problem("sequential", "Two measurements, one projection", "Quantum measurement",
                "In an orthonormal basis |a⟩, |b⟩, |c⟩, prepare |ψ⟩ = (√2|a⟩ + i√3|b⟩ + √5|c⟩)/√10. Measure M = diag(1,1,−1) using the Lüders projection rule. Given outcome +1, find the probability that a subsequent measurement of H = diag(ε,4ε,9ε), ε > 0, returns 4ε. Also find the joint probability of both outcomes.",
                "Ideal projective measurements; use the Lüders rule within the degenerate M = +1 subspace. ε > 0; no intervening evolution.",
                {"epsilon": pos}, [{"epsilon": "2"}, {"epsilon": "3"}], [
            ("Probability of the first outcome", "Add the populations in the a and b basis states.", "P(M = +1)", "1/2", "probability"),
            ("Renormalise the projection", "Multiply the projected state by the inverse square root of its squared norm.", "normalisation multiplier", "sqrt(2)", "probability"),
            ("Conditional b amplitude", "Apply this multiplier to the original b amplitude; the c component is removed.", "c′_b", "I*sqrt(3/5)", "probability"),
            ("Conditional energy probability", "Take the squared magnitude of the b amplitude after projection.", "P(H = 4ε | M = +1)", "3/5", "probability"),
            ("Joint probability", "Multiply the first-outcome probability by the conditional energy probability.", "P(M = +1, H = 4ε)", "3/10", "probability")])
    ]}
    # Non-identical expressions can represent the SAME solution family when
    # arbitrary constants are renamed. Scalar equivalence is insufficient here.
    # Keep arithmetic controls, but exclude error edits at these two steps.
    for p in result["problems"]:
        for step in p["steps"]:
            step["mutation_scope"] = "fixed_claim"
        if p["id"] in {"nonlinear-ode", "euler-cauchy"}:
            p["steps"][2]["mutation_scope"] = "arbitrary_constant_family"
            p["steps"][2]["mutation_note"] = "Error mutations are excluded: changing an arbitrary integration constant can preserve the solution family without being a scalar identity."
    return result


if __name__ == "__main__":
    output = ROOT / "data" / "problems.json"
    output.write_text(json.dumps(dataset(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {output}")
