import re
from lxml import html
from lxml.html.clean import Cleaner
from urllib.parse import urlparse
from urllib.parse import urldefrag
from urllib.parse import urljoin
from urllib.parse import parse_qs
import datetime
import os
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords

# you may need to download nltk data in order to make use of the nltk functionality
nltk.download('stopwords')

# domains that are valid to crawl
valid_domains = "ics.uci.edu|cs.uci.edu|informatics.uci.edu|stat.uci.edu|today.uci.edu/department" \
                "/information_computer_sciences"
# invalid file types which should be skipped
invalid_types = "css|js|bmp|gif|jpe?g|ico" \
                "|png|tiff?|mid|mp2|mp3|mp4" \
                "|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf" \
                "|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names" \
                "|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso" \
                "|epub|dll|cnf|tgz|sha1|php" \
                "|thmx|mso|arff|rtf|jar|csv|xml" \
                "|rm|smil|wmv|swf|wma|zip|rar|gz"
# enable logging
logging = True
# output file
output = None
# data file name
data_path = "data.txt"
# separator string
separator = "#" * 10 + "\n"
# min text size of a page to analyze
min_size = 0
# max size of a page to analyze
max_size = 1e6
# min portion(%) of a page that should be text
min_part = 0.1
# used to get list of tokens in a page, commented out for now
# tokenFile = None
# dict mapping all tokens to total frequency 
word_dict = {}
# top 50 words by frequency
sorted_words = []
# List of pages with largest token count
pages_max = []
max_len = -1
# List of unique pages
unique_pages = set()
# dictionary of subdomains found
subdomain_dic = {}
# sorted list of sub-domains
sorted_domains = []
# count of unique pages
count_url = 0
# unique page count
unique_count = 0


def scraper(url, resp):
    # update unique count
    global unique_count
    unique_count += 1
    # check sub-domain of the the url
    calculate_subdomain(url, '.ics.uci.edu')
    links = extract_next_links(url, resp)
    # check if any links were returned
    if not links:
        return list()
    urls = []
    for link in links:
        # parse the url
        parsed = urlparse(link)
        # separate the queries
        queries = parse_qs(parsed.query, keep_blank_values=False)
        # check if the link is a redirect to another url
        if "url" in queries:
            link = queries["url"][0]
        else:
            # remove queries
            link = urljoin(link, parsed.path)
        if is_valid(link):
            # append the url with fragment removed
            urls.append(urldefrag(link)[0])
    return urls


def extract_next_links(url, resp):
    if resp.status == 200:
        # get total size of page
        page_size = len(resp.raw_response.content)
        # check to see if page is to large, if so skip it
        if page_size > max_size:
            return []
        # convert content into html data
        parser = html.HTMLParser(remove_blank_text=True)
        data = html.document_fromstring(resp.raw_response.content, parser)
        # clean the document
        cleaner = Cleaner(style=True)
        cleaned = cleaner.clean_html(data)
        text = cleaned.text_content()
        text_size = len(text)
        # check if enough text content exists on page
        # if not skip analysis of this page
        if text_size < min_size or text_size / page_size < min_part:
            return []
        # tokenize the text on the page
        tk = tokenize_words(url, text)
        # check if page length(token count) and compare with other pages
        page_length(url, len(tk))
        # update the total frequencies of all words from all crawled pages
        word_frequencies(tk)
        log(f"{resp.status} - {url} - {text_size}/{page_size}\n")
        # return all the links in the page
        return [link for element, attribute, link, pos in data.iterlinks()]
    else:
        log(f"{resp.status} - {url} - {resp.error}\n")
    return list()


def is_valid(url):
    try:
        parsed = urlparse(url)
        # Check if valid http/https link
        if parsed.scheme not in set(["http", "https"]):
            return False
        path = parsed.path.lower()
        # Check if not a web page
        if re.match(
                rf".*\.({invalid_types})$", path):
            return False
        # check if path contains file type
        for part in path.split("/"):
            if re.match(rf"^({invalid_types})$", part):
                return False
        # Check if a valid domain
        return re.search(rf"({valid_domains})", url)
    except TypeError:
        print("TypeError for ", parsed)
        raise


# outputs message to a log file
def log(message):
    # if logging disabled, do not output anything
    if not logging:
        return
    global output
    # open log file if not already open
    if not output:
        # ensure data folder exists
        if not os.path.isdir('data'):
            os.mkdir('data')
            # open log file
        output = open(f"data/{datetime.datetime.now()}.txt", "w")
    # write message to file
    output.write(message)
    # flush file to save output
    output.flush()

    
# uses nltk word_tokenizer to tokenize the text from a url, returns a list of tokens
def tokenize_words(url, text):
    # preprocessing step, converts all characters to lowercase
    words = text.replace("  ", " ").replace("\n", " ").lower().strip()
    # the tokenizing step
    tokens = word_tokenize(words)
    # this is the list of valid tokens
    ftokens = []
    # iterates through full token list to filter out invalid tokens
    for t in tokens:
        # do not include the token if it is a stopword
        if t in stopwords.words():
            continue
        # do not include the token if there are no alphanumeric characters
        if not re.match('[A-Za-z0-9]+', t):
            continue
        ftokens.append(t)
    # the commented code below is for recording the tokens and text from each page;
    # not necessary for the assignment, but kept for reference
    # global tokenFile
    # if not tokenFile:
    #    tokenFile = open("tokenFile.txt", "w")
    # tokenFile.write(str(url) + ": " + str(ftokens) + "\n")
    # tokenFile.write(str(url) + ": " + words + "\n")
    # tokenFile.flush()
    # write sorted file mapping URL's to page length (# of valid tokens)
    return ftokens


# evaluates the page length of a url (# of valid tokens), updates to a dictionary that tracks page lengths for all urls
# also returns the page length
def page_length(url, length):
    global max_len
    if length < max_len:
        return
    global pages_max
    if length == max_len:
        pages_max.append(url)
    else:
        pages_max = list(url)
        max_len = length
    # call pageLen dict
    # global pageLen
    # creates dict if it does not exist yet, creates folder for word_data if it does not exist yet
    # if not pageLen:
    #    if not os.path.isdir('word_data'):
    #        os.mkdir('word_data')
    #    pageLen = {}
    #    pageLen[url] = len(ftokens)
    # else:
    #    # only updates dict if current page length is greater than or equal to the longest page length found so far
    #    longPage = max(pageLen, key=pageLen.get)
    #    if len(ftokens) > pageLen[longPage]:
    #        pageLen = {}
    #        pageLen[url] = len(ftokens)
    #    elif len(ftokens) == pageLen[longPage]:
    #            pageLen[url] = len(ftokens)
    #    else:
    #        return len(ftokens)
    # update pageLen dict
    # pageLenFile = open("word_data/pageLengths.csv", 'w')
    # for i in pageLen:
    #    toWrite = i + "," + str(pageLen[i]) + "\n"
    #    pageLenFile.write(toWrite)
    # pageLenFile.close()
    # return page length
    # return len(ftokens)


# updates word frequency dict with words from current page    
def word_frequencies(ftokens):
    # call wordFreq dict
    global word_dict
    # creates dict if it does not exist yet, creates folder for word_data if it does not exist yet
    # update wordFreq dict, iterates through each token in token list
    for t in ftokens:
        if t not in word_dict:
            word_dict[t] = 0
        word_dict[t] += 1
    # Get top 50 words
    global sorted_words
    sorted_words = sorted(word_dict.items(), key=lambda item: item[1], reverse=True)[:50]


# calculate the subdomains For Question4
def calculate_subdomain(url, suffix):
    parsed = urlparse(url)
    current_page_domain = parsed.netloc
    global subdomain_dic
    if current_page_domain.endswith(suffix) and not current_page_domain.endswith('www.ics.uci.edu'):
        if current_page_domain in subdomain_dic:
            subdomain_dic[current_page_domain] += 1
        else:
            subdomain_dic[current_page_domain] = 1
    global sorted_domains
    sorted_domains = sorted(subdomain_dic.keys(), key=lambda x: x.lower(), reverse=True)


# writes all data needed for questions 1-4 into single file
def write_data():
    if os.path.exists(data_path):
        os.remove(data_path)
    with open(data_path, "w") as data_file:
        # write count of unique pages (question 1)
        data_file.write(f"unique: {count_url}\n")
        data_file.write(separator)
        # write longest page(s) (question 2)
        data_file.write("Longest Page(s)\n")
        for page in pages_max:
            data_file.write(f"{page}, {max_len}\n")
        data_file.write(separator)
        # write top 50 words (question 3)
        data_file.write("Most Common Words\n")
        for word in sorted_words:
            data_file.write(f"{word[0]}, {word[1]}\n")
        data_file.write(separator)
        # write unique sub-domains (question 4)
        data_file.write("Unique Sub-Domains\n")
        for domain in sorted_domains:
            data_file.write(f"{domain[0]}, {domain[1]}\n")
        data_file.write(separator)
