//# SPDX-FileCopyrightText: 2024 Deutsche Telekom AG
//#
//# SPDX-License-Identifier: CC0-1.0

// Initialize MathJax for mathematical expressions
window.MathJax = {
  tex: {
    inlineMath: [["\\(", "\\)"]],
    displayMath: [["\\[", "\\]"]],
    processEscapes: true,
    processEnvironments: true
  },
  options: {
    ignoreHtmlClass: ".*|",
    processHtmlClass: "arithmatex"
  }
};

// Add custom behaviors when DOM is loaded
document.addEventListener("DOMContentLoaded", function() {
  // Enhance navigation
  enhanceNavigation();

  // Add custom interactions
  addCustomInteractions();
});

function enhanceNavigation() {
  // Add smooth scrolling to internal links
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
      e.preventDefault();
      const target = document.querySelector(this.getAttribute('href'));
      if (target) {
        target.scrollIntoView({
          behavior: 'smooth',
          block: 'start'
        });
      }
    });
  });
}

function addCustomInteractions() {
  // Add hover effects to cards
  document.querySelectorAll('.km-card').forEach(card => {
    card.addEventListener('mouseenter', function() {
      this.style.transform = 'translateY(-2px)';
    });

    card.addEventListener('mouseleave', function() {
      this.style.transform = 'translateY(0)';
    });
  });

  // Add copy button functionality to code blocks
  document.querySelectorAll('pre code').forEach(codeBlock => {
    const pre = codeBlock.parentNode;
    if (!pre.querySelector('.copy-button')) {
      const copyButton = document.createElement('button');
      copyButton.className = 'copy-button';
      copyButton.innerHTML = '📋';
      copyButton.title = 'Copy to clipboard';
      copyButton.style.cssText = `
        position: absolute;
        top: 0.5rem;
        right: 0.5rem;
        background: var(--telekom-magenta);
        color: white;
        border: none;
        border-radius: 4px;
        padding: 0.25rem 0.5rem;
        cursor: pointer;
        font-size: 0.8rem;
      `;

      copyButton.addEventListener('click', function() {
        navigator.clipboard.writeText(codeBlock.textContent).then(() => {
          copyButton.innerHTML = '✅';
          setTimeout(() => {
            copyButton.innerHTML = '📋';
          }, 2000);
        });
      });

      pre.style.position = 'relative';
      pre.appendChild(copyButton);
    }
  });
}

// Add analytics or tracking if needed
function initializeAnalytics() {
  // Add your analytics code here
  console.log('Knowledge Management Documentation Portal loaded');
}

// Initialize analytics
initializeAnalytics();
