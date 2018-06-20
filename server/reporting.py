import json
from parsy import regex, seq, string
from urllib.parse import urljoin

'''

filename	string	Required. The name of the file to add an annotation to.
blob_href	string	Required. The file's full blob URL.
start_line	integer	Required. The start line of the annotation.
end_line	integer	Required. The end line of the annotation.
warning_level	string	Required. The warning level of the annotation. Can be one of notice, warning, or failure.
message	string	Required. A short description of the feedback for these lines of code. The maximum size is 64 KB.
title	string	The title that represents the annotation. The maximum size is 255 characters.
raw_details	string	Details about this annotation. The maximum size is 64 KB.

    {
    "filename": "README.md",
    "blob_href": "http://github.com/octocat/Hello-World/blob/837db83be4137ca555d9a5598d0a1ea2987ecfee/README.md",
    "warning_level": "warning",
    "title": "Spell Checker",
    "message": "Check your spelling for 'banaas'.",
    "raw_details": "Do you mean 'bananas' or 'banana'?",
    "start_line": "2",
    "end_line": "2"
    },
'''

TARGETS = set(['pseudo-tested', 'partially-tested'])

def generate_annotations(methods, blob):
    return [annotation_for_method(method, blob) for method in methods if method['classification'] in TARGETS ]


def annotation_for_method(method, blob):
    classification = method['classification']
    assert classification in TARGETS
    annotation = {
        'filename': '',
        'blob_href': '',
        'warning_level': 'failure',
        'title': 'Undetected extreme transformations',
        'message': '',
        'raw_details': '',
        'start_line': '',
        'end_line': ''
    }
    undetected_mutations = [mutant for mutant in method['mutations'] if mutant['status'] == 'SURVIVED']
    annotation['filename'] = method['file-name'] 
    annotation['blob_href'] = urljoin(blob, 'src/main/java/{}/{}'.format(method['package'], method['file-name']))
    annotation['start_line'] = annotation['end_line'] = method['line-number']
    covering_test_cases = len(method['tests'])
    assert covering_test_cases > 0
    if covering_test_cases > 1:
        annotation['raw_details'] = 'This method is covered by ' + ( 'only one test case.' if covering_test_cases == 1 else '{} test cases.'.format(covering_test_cases))
    if 'void' in method['not-detected']:
        assert classification == 'pseudo-tested' and len(method['mutations']) == 1 # There should be only one mutation and the method should be pseudo-tested
        annotation['message'] = 'The body of this method can be removed and no test case fails.'
        return annotation
    transformations = list(transformations_for_method(method))
    if len(transformations) == 1:
        annotation['message'] = 'The body of this method has been replaced by {} and it was not detected by the test suite.'.format(transformations[0])
        return annotation
    annotation['message'] = 'The body of this method has been replaced by the following variants: {} None of these variants was detected by the test suite'.format(''.join(transformations))
    return annotation

    
def transformations_for_method(method):
    for mutant in method['mutations']:
        assert mutant['mutator'] != 'void'
        if mutant['status'] != 'SURVIVED':
            continue
        value = mutant['mutator'] if mutant['mutator'] != 'empty' else get_array_value(method)
        yield '\n``` return {}; ```\n'.format(value)

def get_array_value(method):
    _, return_type = PARSER.parse(method['description'])
    return 'new ' + return_type

BASE_TYPE_NAMES = {
    'B': "byte",
    'C': "char",
    'D': "double",
    'F': "float",
    'I': "int",
    'J': "long",
    'S': "short",
    'Z': "boolean",
}

def description_parser():
    point_join = lambda *args: '.'.join(args)
    identifier = regex(r'[0-9a-zA-Z\$_]+')
    class_name = string('L') >> identifier.sep_by(string('/')).combine(point_join) << string(';')
    base_type = regex('[BCDFIJSZ]').map(lambda i: BASE_TYPE_NAMES[i])
    array = seq(string('[').at_least(1).map(lambda o: '[]' * len(o)), (base_type | class_name)).combine(lambda o, t: t + o)
    parameter = base_type | class_name | array
    parameters = parameter.many().combine(lambda *args: '(' + ','.join(args) + ')' )
    void = string('V').map(lambda v: 'void')
    return_type =  void | parameter
    return seq(string('(') >> parameters << string(')'), return_type)

PARSER = description_parser()        
