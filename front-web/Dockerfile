FROM nginx:1.27-alpine

# Remove default nginx static files.
RUN rm -rf /usr/share/nginx/html/*

# Copy exported frontend assets into nginx web root.
COPY . /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
