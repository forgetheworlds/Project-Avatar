For 2026 engineering economic analysis, decision-making relies on converting varying cash flows into comparable formats. Key formulas focus on standardizing costs over time, accounting for asset devaluation, and adjusting for market conditions like inflation and taxes. 

1. Equivalent Annual Cost (EAC) 

EAC (or EUAC) converts an investment’s **Net Present Value (NPV)** into a uniform annual stream. It is essential for comparing projects with **unequal lifespans**. 

* **Formula**:
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mi>E</mi><mi>A</mi><mi>C</mi><mo>=</mo><mfrac><mrow><mi>N</mi><mi>P</mi><mi>V</mi></mrow><mrow><mi>A</mi><mo>(</mo><mi>t</mi><mo>,</mo><mi>r</mi><mo>)</mo></mrow></mfrac><mo>=</mo><mfrac><mrow><mi>N</mi><mi>P</mi><mi>V</mi><mo>⋅</mo><mi>r</mi></mrow><mrow><mn>1</mn><mo>−</mo><mo>(</mo><mn>1</mn><mo>+</mo><mi>r</mi><msup><mo>)</mo><mrow><mo>−</mo><mi>n</mi></mrow></msup></mrow></mfrac></mrow><annotation encoding="text/plain">cap E cap A cap C equals the fraction with numerator cap N cap P cap V and denominator cap A open paren t comma r close paren end-fraction equals the fraction with numerator cap N cap P cap V center dot r and denominator 1 minus open paren 1 plus r close paren raised to the negative n power end-fraction</annotation></semantics></math> --> EAC=NPVA(t,r)=NPV⋅r1−(1+r)−ncap E cap A cap C equals the fraction with numerator cap N cap P cap V and denominator cap A open paren t comma r close paren end-fraction equals the fraction with numerator cap N cap P cap V center dot r and denominator 1 minus open paren 1 plus r close paren raised to the negative n power end-fraction

Where:
  +
      
      <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mi>N</mi><mi>P</mi><mi>V</mi></mrow><annotation encoding="text/plain">cap N cap P cap V</annotation></semantics></math> --> NPVcap N cap P cap V

: Net Present Value of all costs (initial price + PV of maintenance - PV of salvage).
  +
      
      <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mi>r</mi><annotation encoding="text/plain">r</annotation></semantics></math> --> rr

: Discount rate (cost of capital).
  +
      
      <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mi>n</mi><annotation encoding="text/plain">n</annotation></semantics></math> --> nn

: Asset's lifespan in years.
* **Example**: An asset costs $100,000, lasts 5 years, and has $4,000 annual maintenance. At a 5% discount rate:
  1. Annuity Factor

  2. 

2. Depreciation Methods 

Depreciation allocates the capital cost of an asset over its life for tax purposes. 

* **Straight-Line (SL)**: Constant annual deduction.
  + **Formula**:

  + **Example**: $15,000 truck, $5,000 salvage, 5-year life
      
      <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mo>→</mo><msub><mi>D</mi><mi>t</mi></msub><mo>=</mo><mfrac><mrow><mn>15000</mn><mo>−</mo><mn>5000</mn></mrow><mn>5</mn></mfrac><mo>=</mo><mo>$</mo><mn>2</mn><mo>,</mo><mn>000</mn><mo>/</mo><mtext>year</mtext></mrow><annotation encoding="text/plain">right arrow cap D sub t equals the fraction with numerator 15000 minus 5000 and denominator 5 end-fraction equals $ 2 comma 000 / year</annotation></semantics></math> --> →Dt=15000−50005=$2,000/yearright arrow cap D sub t equals the fraction with numerator 15000 minus 5000 and denominator 5 end-fraction equals $ 2 comma 000 / year

* **Declining Balance (DB)**: Accelerated depreciation based on a fixed percentage of the current **Book Value (BV)**.
  + **Formula**:

  + **Book Value**:

  +
      
      <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mi>k</mi><annotation encoding="text/plain">k</annotation></semantics></math> --> kk is often for Double Declining Balance.
* **MACRS (IRS Standard)**: Uses statutory percentage tables based on DB or SL methods with a **half-year convention** (first and last years count as half).
  + **Formula**:

  + **Note**: Salvage value is assumed to be **zero** under MACRS. 

3. Bond Pricing 

Bond value is the present worth of future coupon payments (annuity) plus the face value (lump sum). 

* **Formula**:
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mi>P</mi><mo>=</mo><mi>C</mi><mo>⋅</mo><mrow><mo>[</mo><mfrac><mrow><mn>1</mn><mo>−</mo><mo>(</mo><mn>1</mn><mo>+</mo><mi>i</mi><msup><mo>)</mo><mrow><mo>−</mo><mi>n</mi></mrow></msup></mrow><mi>i</mi></mfrac><mo>]</mo></mrow><mo>+</mo><mfrac><mi>F</mi><mrow><mo>(</mo><mn>1</mn><mo>+</mo><mi>i</mi><msup><mo>)</mo><mi>n</mi></msup></mrow></mfrac></mrow><annotation encoding="text/plain">cap P equals cap C center dot open bracket the fraction with numerator 1 minus open paren 1 plus i close paren raised to the negative n power and denominator i end-fraction close bracket plus the fraction with numerator cap F and denominator open paren 1 plus i close paren to the n-th power end-fraction</annotation></semantics></math> --> P=C⋅[1−(1+i)−ni]+F(1+i)ncap P equals cap C center dot open bracket the fraction with numerator 1 minus open paren 1 plus i close paren raised to the negative n power and denominator i end-fraction close bracket plus the fraction with numerator cap F and denominator open paren 1 plus i close paren to the n-th power end-fraction

Where:
  +
      
      <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mi>P</mi><annotation encoding="text/plain">cap P</annotation></semantics></math> --> Pcap P

: Current market price.
  +
      
      <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mi>C</mi><annotation encoding="text/plain">cap C</annotation></semantics></math> --> Ccap C

: Periodic coupon payment (
      
      
).
  +
      
      <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mi>F</mi><annotation encoding="text/plain">cap F</annotation></semantics></math> --> Fcap F

: Face (par) value.
  +
      
      <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mi>i</mi><annotation encoding="text/plain">i</annotation></semantics></math> --> ii

: Required market interest rate (yield) per period.
  +
      
      <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mi>n</mi><annotation encoding="text/plain">n</annotation></semantics></math> --> nn

: Total number of payment periods. 

4. Inflation Adjustment 

Inflation separates "real" dollars (constant purchasing power) from "market" (actual) dollars. 

* **Fisher Equation**:
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mo>(</mo><mn>1</mn><mo>+</mo><msub><mi>i</mi><mi>m</mi></msub><mo>)</mo><mo>=</mo><mo>(</mo><mn>1</mn><mo>+</mo><msub><mi>i</mi><mi>r</mi></msub><mo>)</mo><mo>(</mo><mn>1</mn><mo>+</mo><mi>f</mi><mo>)</mo></mrow><annotation encoding="text/plain">open paren 1 plus i sub m close paren equals open paren 1 plus i sub r close paren open paren 1 plus f close paren</annotation></semantics></math> --> (1+im)=(1+ir)(1+f)open paren 1 plus i sub m close paren equals open paren 1 plus i sub r close paren open paren 1 plus f close paren

Where:
  +
      
      <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>i</mi><mi>m</mi></msub><annotation encoding="text/plain">i sub m</annotation></semantics></math> --> imi sub m
: Market interest rate (includes inflation).
  +
      
      <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>i</mi><mi>r</mi></msub><annotation encoding="text/plain">i sub r</annotation></semantics></math> --> iri sub r
: Real interest rate.
  +
      
      <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mi>f</mi><annotation encoding="text/plain">f</annotation></semantics></math> --> ff
: Inflation rate. `[1][2][3]`

5. After-Tax Cash Flow (ATCF) 

ATCF measures the actual cash available after meeting tax obligations. 

* **Taxable Income**:

* **Income Tax**:

* **ATCF Formula**:
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mi>A</mi><mi>T</mi><mi>C</mi><mi>F</mi><mo>=</mo><mtext>Revenue</mtext><mo>−</mo><mtext>Expenses</mtext><mo>−</mo><mi>T</mi><mi>a</mi><mi>x</mi></mrow><annotation encoding="text/plain">cap A cap T cap C cap F equals Revenue minus Expenses minus cap T a x</annotation></semantics></math> --> ATCF=Revenue−Expenses−Taxcap A cap T cap C cap F equals Revenue minus Expenses minus cap T a x

OR
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mi>A</mi><mi>T</mi><mi>C</mi><mi>F</mi><mo>=</mo><mo>(</mo><mtext>Revenue</mtext><mo>−</mo><mtext>Expenses</mtext><mo>)</mo><mo>(</mo><mn>1</mn><mo>−</mo><mi>T</mi><mo>)</mo><mo>+</mo><mo>(</mo><mtext>Depreciation</mtext><mo>⋅</mo><mi>T</mi><mo>)</mo></mrow><annotation encoding="text/plain">cap A cap T cap C cap F equals open paren Revenue minus Expenses close paren open paren 1 minus cap T close paren plus open paren Depreciation center dot cap T close paren</annotation></semantics></math> --> ATCF=(Revenue−Expenses)(1−T)+(Depreciation⋅T)cap A cap T cap C cap F equals open paren Revenue minus Expenses close paren open paren 1 minus cap T close paren plus open paren Depreciation center dot cap T close paren

*(Where
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mi>T</mi><annotation encoding="text/plain">cap T</annotation></semantics></math> --> Tcap T is the tax rate)*. 

Would you like a sample **spreadsheet layout** for an after-tax cash flow analysis? 

AI can make mistakes, so double-check responses

Copy

Creating a public link...

Good response

Bad response

Saved time

Clear

Helpful

Comprehensive

Other

Incorrect

Inappropriate

Not working

Unhelpful

Other

A copy of this chat will be included with your feedback

A copy of this chat and your uploaded image will be included with your feedback

Your feedback will include a copy of this chat, any links you shared, and the image from your search.

Thanks for letting us know

Google may use account and system data to understand your feedback and improve our services, subject to our [Privacy Policy](https://policies.google.com/privacy) and [Terms of Service](https://policies.google.com/terms). For legal issues, [make a legal removal request](https://support.google.com/legal/answer/3110420).

---

## Sources:

[1] Understanding Equivalent Annual Cost (EAC) for Capital .... Opens in new tab.  
https://www.investopedia.com/terms/e/eac.asp#:~:text=EAC%20=%20Asset%20Price%20%C3%97%20Discount,n=Number%20of%20periods%EF%BB%BF

[2] The Equivalent Annual Cost (EAC) Method: A Numerical .... Opens in new tab.  
https://www.youtube.com/watch?v=XwU1utmNGHk

[3] A Brief Guide to Engineering Financial Calculations. Opens in new tab.  
https://engcourses-uofa.ca/books/introduction-to-engineering-economics/a-brief-guide-to-engineering-financial-calculations/#:~:text=Straight%2DLine%20Method:,year%20is%20the%20original%20value%20).

