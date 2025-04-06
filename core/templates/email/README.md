# Email Template System

This directory contains the email templates used throughout the RebatOn platform.

## Structure

- `base_email.html` - Base template with common structure and styling
- `styles.css` - Shared CSS styles for all email templates
- Individual email templates extending the base template

## Template Blocks

The base template provides the following blocks that can be overridden:

- `header` - Header section (defaults to title)
- `content` - Main content area
- `action` - Call to action section
- `footer` - Footer section with copyright and unsubscribe link

## CSS Components

### Layout
- `.container` - Main container
- `.header` - Header section
- `.content` - Content section
- `.footer` - Footer section

### Typography
- `.text-center` - Center-aligned text
- `.text-muted` - Muted text color
- `.text-small` - Small text (14px)
- `.text-large` - Large text (18px)

### Components
- `.button` - Call to action button
- `.deal-card` - Deal information card
- `.alert` - Alert messages
- `.alert-info` - Info alert variant
- `.alert-success` - Success alert variant
- `.alert-warning` - Warning alert variant

### Spacing
- `.mt-20` - Margin top 20px
- `.mb-20` - Margin bottom 20px

## Usage Example

```html
{% extends "base_email.html" %}

{% block content %}
<div class="text-center">
    <h2>Title</h2>
    <p class="text-large">Message</p>
    
    <div class="deal-card">
        <!-- Deal information -->
    </div>
</div>
{% endblock %}

{% block action %}
<div class="text-center">
    <a href="{{ action_url }}" class="button">Action Button</a>
</div>
{% endblock %}
```

## Best Practices

1. Always extend the base template
2. Use provided CSS classes instead of inline styles
3. Keep templates focused and single-purpose
4. Use proper semantic HTML structure
5. Test emails in multiple clients
6. Include both HTML and plain text versions
7. Keep images to a minimum
8. Use responsive design classes

## Email Client Compatibility

The templates are designed to work across major email clients:
- Gmail
- Outlook
- Apple Mail
- Yahoo Mail
- Mobile email clients

CSS is included both as an external file and inlined in the base template for maximum compatibility. 