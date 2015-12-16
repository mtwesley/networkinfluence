import os
import pandas
import numpy
import networkx
from networkx.readwrite import json_graph

import config

import pyexcel
import pyexcel.ext.xls
import pyexcel.ext.xlsx

import json

from flask import Flask, render_template, request, send_from_directory, jsonify

app = Flask(__name__, static_url_path='')
app.config.from_object(config)


@app.route('/network/<name>')
def network_name(name):
    directory = os.path.dirname(os.path.abspath(__file__))
    return send_from_directory(os.path.join(directory, 'networks'), name + '.json', mimetype='application/json')


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST' and 'excel' in request.files:

        # handle file upload
        network_name = request.form.get('network', None)
        filename = request.files['excel'].filename
        extension = filename.split(".")[1]

        # parse file into excel data
        sheet = pyexcel.get_sheet(file_type=extension, file_content=request.files['excel'].read())

        # column and row titles
        title = sheet[0, 0].strip()
        agents = [k.strip() for k in sheet.column[0] if k.strip() and k != sheet[0, 0]]
        types = [k.strip() for k in sheet.row[0] if k.strip() and 'Weight' not in k and k != sheet[0, 0]]

        # print 'Agents: ', agents, "\n\n"
        # print 'Types: ', types, "\n\n"

        # name sheet columns and create objects
        sheet.name_columns_by_row(0)
        records = pyexcel.to_records(sheet)

        # print 'Records: ', json.dumps(records), "\n\n\n"

        # all organization values and weights
        organizations = set()
        weights = {}
        data = {}

        for record in records:
            for key, value in record.items():
                if not key:
                    continue

                if key == title:
                    continue

                if 'Weight' in key:
                    _index = key.index('Weight') - 1
                    _key = key[:_index]
                    weights[_key] = value

                elif value and value not in agents:
                    if value not in data:
                        data[value.strip()] = {}

                    data[value.strip()][record[title].strip()] = int(record[key + ' Weight'])
                    organizations.add(value.strip())

        # preparing D3.js output
        d3 = dict()
        d3['matrix1'] = {'nodes': [], 'links': []}
        d3['matrix2'] = {'nodes': [], 'links': []}
        d3['matrix3'] = {'nodes': [], 'links': []}
        d3['matrix4'] = {'nodes': [], 'links': []}

        # build data frame to hold information
        df1 = pandas.DataFrame(index=agents, columns=organizations, data=data).fillna(0)

        # transpose data frame
        df2 = df1.T

        # convert data frames to matrix
        m1 = df1.as_matrix()
        m2 = df2.as_matrix()

        # conduct matrix multiplication
        m3 = numpy.dot(m1, m2)
        m4 = numpy.dot(m2, m1)

        # fix multiplication, zero-ing agent-to-themselves
        df3 = pandas.DataFrame(index=agents, columns=agents, data=m3)
        for agent in agents:
            d3['matrix1']['nodes'].append({'id': agent})
            d3['matrix2']['nodes'].append({'id': agent})
            d3['matrix3']['nodes'].append({'id': agent})
            d3['matrix4']['nodes'].append({'id': agent})
            df3[agent][agent] = 0

        # fix multiplication, zero-ing organization-to-themselves
        df4 = pandas.DataFrame(index=organizations, columns=organizations, data=m4)
        for organization in organizations:
            df4[organization][organization] = 0

        # network 1
        n1 = networkx.Graph()
        n1.add_nodes_from(agents)
        n1.add_nodes_from(organizations)
        for organization in organizations:
            for agent in agents:
                if agent in df1[organization]:
                    weight = df1[organization][agent]
                    if isinstance(weight, (int, long, float, complex)) and weight:
                        d3['matrix1']['links'].append({'source': agent,
                                                       'target': organization,
                                                       'weight': weight})
                        n1.add_edge(agent, organization, weight=weight)

        networkx.set_node_attributes(n1, 'influencer', None)
        networkx.set_node_attributes(n1, 'connector', None)
        networkx.set_node_attributes(n1, 'degree', None)

        # network 2
        n2 = networkx.Graph()
        n2.add_nodes_from(agents)
        n2.add_nodes_from(organizations)
        for agent in agents:
            for organization in organizations:
                if organization in df2[agent]:
                    weight = df2[agent][organization]
                    if isinstance(weight, (int, long, float, complex)) and weight:
                        d3['matrix2']['links'].append({'source': organization,
                                                       'target': agent,
                                                       'weight': weight})
                        n2.add_edge(organization, agent, weight=weight)

        networkx.set_node_attributes(n2, 'influencer', None)
        networkx.set_node_attributes(n2, 'connector', None)
        networkx.set_node_attributes(n2, 'degree', None)

        # network 3
        n3 = networkx.Graph()
        n3.add_nodes_from(agents)
        for agent1 in agents:
            for agent2 in agents:
                if not (agent1 in n3 and agent2 in n3[agent1]):
                    if agent2 in df3[agent1]:
                        df3[agent1][agent2] = 0
                        weight = df3[agent1][agent2]
                        if isinstance(weight, (int, long, float, complex)) and weight:
                            d3['matrix3']['links'].append({'source': agent1,
                                                           'target': agent2,
                                                           'weight': weight})
                            n3.add_edge(agent1, agent2, weight=weight)

        networkx.set_node_attributes(n3, 'influencer', networkx.eigenvector_centrality(n3))
        networkx.set_node_attributes(n3, 'connector', networkx.betweenness_centrality(n3))
        networkx.set_node_attributes(n3, 'degree', networkx.degree_centrality(n3))

        # network 4
        n4 = networkx.Graph()
        n4.add_nodes_from(organizations)
        for organization1 in organizations:
            for organization2 in organizations:
                if not (organization1 in n4 and organization2 in n4[organization1]):
                    if organization2 in df4[organization1]:
                        weight = df4[organization1][organization2]
                        if isinstance(weight, (int, long, float, complex)) and weight:
                            d3['matrix4']['links'].append({'source': organization1,
                                                           'target': organization2,
                                                           'weight': weight})
                            n4.add_edge(organization1, organization2, weight=weight)

        networkx.set_node_attributes(n4, 'influencer', networkx.eigenvector_centrality(n4))
        networkx.set_node_attributes(n4, 'connector', networkx.betweenness_centrality(n4))
        networkx.set_node_attributes(n4, 'degree', networkx.degree_centrality(n4))

        network_filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'networks', network_name + '.json')
        with open(network_filepath, 'w') as outfile:
            json.dump({
                'n1': json_graph.node_link_data(n1),
                'n2': json_graph.node_link_data(n2),
                'n3': json_graph.node_link_data(n3),
                'n4': json_graph.node_link_data(n4)
            }, outfile, sort_keys=True, indent=4, separators=(',', ': '))

        return 'Done'

        # render_template('index.html',
        #                        data=True,
        #                        df1=df1.to_html(),
        #                        df2=df2.to_html(),
        #                        df3=df3.to_html(),
        #                        df4=df4.to_html(),
        #                        n1=json.dumps(json_graph.node_link_data(n1)),
        #                        n2=json.dumps(json_graph.node_link_data(n2)),
        #                        n3=json.dumps(json_graph.node_link_data(n3)),
        #                        n4=json.dumps(json_graph.node_link_data(n4)))

        # return jsonify(
                               # data=True,
                               # # df1=df1.to_html(),
                               # # df2=df2.to_html(),
                               # # df3=df3.to_html(),
                               # # df4=df4.to_html(),
                               # n1=json_graph.node_link_data(n1),
                               # n2=json_graph.node_link_data(n2),
                               # n3=json_graph.node_link_data(n3),
                               # n4=json_graph.node_link_data(n4))

        # import matplotlib.pyplot as plt
        # networkx.draw(n3, with_labels=True)
        # plt.savefig('plot-n3.png')

        # networkx.draw(n4)
        # plt.savefig('plot-n4.png')


        return render_template('index.html', json=json.dumps(d3['matrix1']))

    network_name = request.args.get('network', None)

    filepath =  os.path.join(os.path.dirname(os.path.abspath(__file__)), 'networks')
    files = [n[:-5] for n in next(os.walk(filepath))[2]]

    return render_template('index.html', network_name=network_name, files=files)



